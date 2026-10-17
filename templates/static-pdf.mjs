// One-page raster PDF, matching the existing PNG-based local PDF export.
// Japanese text is rasterized by the browser with the same fonts as the chart.
export function jpegPdf(bytes,width,height) {
  if (!(width>0&&height>0)) throw Error('画像サイズが不正です。');
  const enc=new TextEncoder(),parts=[],offsets=[0];let length=0;
  const add=b=>{if(typeof b==='string')b=enc.encode(b);parts.push(b);length+=b.length};
  const object=(n,body)=>{offsets[n]=length;add(`${n} 0 obj\n`);add(body);add('\nendobj\n')};
  const scale=Math.min(1,14400/width,14400/height),w=width*scale,h=height*scale;
  add('%PDF-1.4\n');
  object(1,'<< /Type /Catalog /Pages 2 0 R >>');
  object(2,'<< /Type /Pages /Kids [3 0 R] /Count 1 >>');
  object(3,`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`);
  offsets[4]=length;add(`4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${width} /Height ${height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${bytes.length} >>\nstream\n`);add(bytes);add('\nendstream\nendobj\n');
  const content=`q ${w} 0 0 ${h} 0 0 cm /Im0 Do Q`;
  object(5,`<< /Length ${enc.encode(content).length} >>\nstream\n${content}\nendstream`);
  const xref=length;add('xref\n0 6\n0000000000 65535 f \n');
  for(let n=1;n<=5;n++)add(String(offsets[n]).padStart(10,'0')+' 00000 n \n');
  add(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  return new Blob(parts,{type:'application/pdf'});
}
export async function chartPdf(image) {
  const img=new Image();img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(image.source);await img.decode();
  const scale=Math.min(2,8192/image.width,8192/image.height),canvas=document.createElement('canvas');
  canvas.width=Math.ceil(image.width*scale);canvas.height=Math.ceil(image.height*scale);
  const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);
  const blob=await new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(Error('PDF用の画像を作成できませんでした。')),'image/jpeg',.96));
  return jpegPdf(new Uint8Array(await blob.arrayBuffer()),canvas.width,canvas.height);
}
