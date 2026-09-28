import hashlib
import math
from datetime import timedelta
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.adapters.embeddings.local import LocalImageEmbedding, LocalTextEmbedding
from app.models import Attachment, FoundItem, ItemEmbedding, LostReport, MatchingResult, ReportStatus
from app.services.matching import score_item

def cosine(a:list[float],b:list[float])->float:
    if not a or not b or len(a)!=len(b): return 0.0
    return max(0.0,min(1.0,sum(x*y for x,y in zip(a,b))))

def confidence(score:int)->str:
    return "HIGH" if score>=75 else "MEDIUM" if score>=45 else "LOW"

def item_text(item)->str:
    return " ".join(str(x) for x in [item.name,item.color,item.brand,item.description,item.location] if x)

def embedding(db:Session,item,entity_type:str,provider)->tuple[list[float],str]:
    text=item_text(item); digest=hashlib.sha256(text.encode()).hexdigest()
    saved=db.scalar(select(ItemEmbedding).where(ItemEmbedding.entity_type==entity_type,ItemEmbedding.entity_id==item.id,ItemEmbedding.kind=="text",ItemEmbedding.provider==provider.identity))
    if saved and saved.content_hash==digest: return saved.vector,provider.identity
    try: vector=provider.embed_text(text); used=provider.identity
    except Exception: vector=LocalTextEmbedding().embed_text(text); used="deterministic-fallback"
    if not saved:
        saved=ItemEmbedding(institution_id=item.institution_id,category_id=item.category_id,entity_type=entity_type,entity_id=item.id,kind="text",provider=provider.identity,content_hash=digest,vector=vector);db.add(saved)
    else: saved.vector=vector;saved.content_hash=digest
    return vector,used

def image_vector(db:Session,item_id:str,entity_type:str,storage,provider)->tuple[list[float]|None,str|None]:
    condition=Attachment.lost_report_id==item_id if entity_type=="lost_report" else Attachment.found_item_id==item_id
    attachment=db.scalar(select(Attachment).where(condition).order_by(Attachment.created_at.desc()))
    if not attachment:return None,None
    try:data=storage.path(attachment.stored_name).read_bytes();return provider.embed_image(data),provider.identity
    except Exception:return None,None

def generate_matches(db:Session,lost:LostReport,storage,text_provider=None,image_provider=None)->list[MatchingResult]:
    if lost.status!=ReportStatus.OPEN or lost.is_archived:
        db.execute(delete(MatchingResult).where(MatchingResult.lost_report_id==lost.id));db.flush();return []
    text_provider=text_provider or LocalTextEmbedding(); image_provider=image_provider or LocalImageEmbedding()
    candidates=db.scalars(select(FoundItem).where(FoundItem.institution_id==lost.institution_id,FoundItem.category_id==lost.category_id,FoundItem.status==ReportStatus.OPEN,FoundItem.is_archived.is_(False),FoundItem.date_found>=lost.date_lost-timedelta(days=90),FoundItem.date_found<=lost.date_lost+timedelta(days=90))).all()
    lost_vector,used=embedding(db,lost,"lost_report",text_provider)
    lost_image,_=image_vector(db,lost.id,"lost_report",storage,image_provider)
    results=[]
    for found in candidates:
        structured,reasons=score_item(found,lost.name,lost.color,lost.location,lost.date_lost)
        found_vector,provider_used=embedding(db,found,"found_item",text_provider)
        semantic=round(cosine(lost_vector,found_vector)*100)
        found_image,image_used=image_vector(db,found.id,"found_item",storage,image_provider)
        image=round(cosine(lost_image,found_image)*100) if lost_image and found_image else 0
        total=round(structured*.55+semantic*.35+image*.10) if image else round(structured*.60+semantic*.40)
        factors=list(reasons)
        if semantic>=35:factors.append("Semantically similar description")
        if image>=40:factors.append("Similar item photograph")
        explanation="Suggested because "+", ".join(x.lower() for x in factors[:4])+"."
        row=db.scalar(select(MatchingResult).where(MatchingResult.lost_report_id==lost.id,MatchingResult.found_item_id==found.id))
        values=dict(structured_score=structured,semantic_score=semantic,image_score=image,total_score=total,confidence=confidence(total),factors=factors,explanation=explanation,provider=provider_used if provider_used!="deterministic-fallback" else used)
        if row:
            for key,value in values.items():setattr(row,key,value)
        else:row=MatchingResult(institution_id=lost.institution_id,lost_report_id=lost.id,found_item_id=found.id,**values);db.add(row)
        results.append(row)
    db.flush();results.sort(key=lambda x:(-x.total_score,x.found_item_id));return results
