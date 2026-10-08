export function portalValues(scroll:number,height:number,reduced=false){
 const p=reduced?1:Math.max(0,Math.min(1,scroll/(height*1.5)));
 return {p,panel:p*106,scale:1+p*.18,tracking:.045-p*.075,split:p*48,image:1.12-p*.12};
}
export function shouldThrow(dx:number,width:number){return Math.abs(dx)>width*.1}
