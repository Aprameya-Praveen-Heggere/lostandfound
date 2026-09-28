export type Role='USER'|'OFFICER'|'ADMIN'
export interface User{id:string;name:string;email:string;role:Role;institution_id:string;is_platform_admin:boolean}
export interface Category{id:string;name:string;slug:string;icon:string}
export interface FoundItem{id:string;reference:string;category_id:string;name:string;description?:string;color?:string;brand?:string;location:string;date_found:string;custody:string;status:string;created_at:string;category:Category;relevance_score?:number;relevance_reasons?:string[]}
export interface LostReport{id:string;reference:string;category_id:string;name:string;description?:string;color?:string;brand?:string;location:string;date_lost:string;status:string;created_at:string;category:Category}
export interface Claim{id:string;found_item_id:string;claimant_id:string;ownership_details:string;status:string;rejection_reason?:string;created_at:string;found_item:FoundItem}
export interface Notification{id:string;title:string;message:string;is_read:boolean;created_at:string}
export interface Match{id:string;lost_report_id:string;found_item_id:string;structured_score:number;semantic_score:number;image_score:number;total_score:number;confidence:'LOW'|'MEDIUM'|'HIGH';factors:string[];explanation:string;provider:string;found_item:FoundItem}
