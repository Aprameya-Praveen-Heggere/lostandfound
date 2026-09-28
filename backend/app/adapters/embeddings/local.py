import hashlib
import math
import re

SYNONYMS={"bag":"backpack","college":"campus","computer":"laptop","sleeve":"compartment","dark":"black","discovered":"found","outside":"near","mobile":"phone","flask":"bottle"}

class LocalTextEmbedding:
    identity="local.semantic-hash"; version="1.0"
    dimensions=96
    def embed_text(self,text:str)->list[float]:
        vector=[0.0]*self.dimensions
        tokens=[SYNONYMS.get(x,x) for x in re.findall(r"[a-z0-9]+",text.lower())]
        for token in tokens:
            digest=hashlib.sha256(token.encode()).digest(); index=int.from_bytes(digest[:2],"big")%self.dimensions
            vector[index]+=1.0
        norm=math.sqrt(sum(x*x for x in vector)) or 1.0
        return [x/norm for x in vector]
    def health(self): return {"status":"healthy","mode":"local"}

class LocalImageEmbedding:
    identity="local.image-histogram"; version="1.0"
    def embed_image(self,data:bytes)->list[float]:
        vector=[0.0]*32
        for value in data: vector[value//8]+=1
        norm=math.sqrt(sum(x*x for x in vector)) or 1.0
        return [x/norm for x in vector]
    def health(self): return {"status":"healthy","mode":"local","face_recognition":False}

class UnavailableEmbedding:
    identity="unavailable"; version="1.0"
    def embed_text(self,text:str): raise RuntimeError("Embedding provider unavailable")
    def embed_image(self,data:bytes): raise RuntimeError("Image embedding provider unavailable")
    def health(self): return {"status":"unavailable"}
