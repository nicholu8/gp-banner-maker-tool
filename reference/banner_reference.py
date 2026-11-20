import sys, argparse, io
from PIL import Image, ImageDraw, ImageFont
SCHEMES={ 'braddock':('#8DC63F','#000000'),'shiloh':('#FFC20E','#000000'),'garden dreams':('#F7941D','#000000'),
 'grc':('#003510','#FFFFFF'),'other':('#981B1E','#FFFFFF')}
F='/home/claude/fonts/Bitter-%d.ttf'
def build(src,out,title,dt,loc,loc_key,cost=None,ratio_h=0.5,yoff=0.5,nowrap=False):
    bg,fg=SCHEMES[loc_key]
    S=2; W=940*S; H=470*S                       # template is 940x470 (2:1); render at 2x
    im=Image.open(src).convert('RGB'); w,h=im.size
    th=int(w*ratio_h)
    if th<=h: top=int((h-th)*yoff); im=im.crop((0,top,w,top+th))
    else: lw=int(h/ratio_h); l=(w-lw)//2; im=im.crop((l,0,l+lw,h))
    im=im.resize((W,H),Image.LANCZOS)
    photo=im.copy()
    line3=f"{loc} | {cost}" if cost else loc
    fs_t,fs_b=34*S,29*S
    maxw=int(W*(0.97 if nowrap else 0.86))
    def fonts(a): return ImageFont.truetype(F%700,a),ImageFont.truetype(F%600,int(a*29/34))
    d=ImageDraw.Draw(im)
    ft,fb=fonts(fs_t)
    tw=lambda t,f:d.textlength(t,font=f)
    # wrap title to 2 lines if needed
    def wrap(t,f):
        if nowrap or tw(t,f)<=maxw-82*S: return [t]
        words=t.split(); best=None
        for i in range(1,len(words)):
            a,b=' '.join(words[:i]),' '.join(words[i:])
            m=max(tw(a,f),tw(b,f))
            if best is None or m<best[0]: best=(m,[a,b])
        return best[1]
    lines=wrap(title,ft)
    while max(tw(l,ft) for l in lines+[dt,line3])>maxw-82*S and fs_t>20*S:
        fs_t-=S; ft,fb=fonts(fs_t); lines=wrap(title,ft)
    rows=[(l,ft) for l in lines]+[(dt,fb),(line3,fb)]
    lh_t,lh_b=int(fs_t*1.5),int(fs_t*29/34*1.5)
    pad_top,pad_bot=int(18*S),int(14*S)
    bh=pad_top+pad_bot+len(lines)*lh_t+2*lh_b-int(8*S)
    bw=int(max(tw(t,f) for t,f in rows)+20*S+62*S)
    bw=min(bw,W)
    # banner w/ antialiased rounded top-right corner
    Q=4; m=Image.new('L',(bw*Q,bh*Q),0); md=ImageDraw.Draw(m)
    r=26*S*Q
    md.rounded_rectangle((-r*2,0,bw*Q-1,bh*Q+r*2),radius=r,fill=255)
    m=m.resize((bw,bh),Image.LANCZOS)
    y0=H-bh
    im.paste(Image.new('RGB',(bw,bh),bg),(0,y0),m)
    d=ImageDraw.Draw(im); y=y0+pad_top
    for t,f in rows:
        lh=lh_t if f is ft else lh_b
        asc,desc=f.getmetrics()
        d.text((20*S,y+(lh-(asc+desc))//2),t,font=f,fill=fg)
        y+=lh
    im.save(out,quality=95) if out.endswith('.jpg') else im.save(out)
    # ---- PDF twin with LIVE text (imports into Canva as editable text) ----
    # built as a temporary PPTX, converted to PDF with LibreOffice, then the PPTX is discarded
    import os, shutil, subprocess, tempfile
    from pptx import Presentation
    from pptx.util import Emu, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN, MSO_AUTO_SIZE
    fd=os.path.expanduser('~/.fonts'); os.makedirs(fd,exist_ok=True)
    for wgt in (600,700): shutil.copy(F%wgt,fd)
    subprocess.run(['fc-cache','-f'],capture_output=True)
    IN=13.333; ppx=W/IN; E=lambda px:Emu(int(px/ppx*914400))
    prs=Presentation(); prs.slide_width=Emu(int(IN*914400)); prs.slide_height=Emu(int(H/ppx*914400))
    sl=prs.slides.add_slide(prs.slide_layouts[6])
    buf=io.BytesIO(); photo.save(buf,'JPEG',quality=92); buf.seek(0)
    sl.shapes.add_picture(buf,0,0,prs.slide_width,prs.slide_height).name='photo'
    sh=sl.shapes.add_shape(MSO_SHAPE.ROUND_1_RECTANGLE,0,E(y0),E(bw),E(H-y0)); sh.name='banner'
    sh.adjustments[0]=(26*S)/min(bw,H-y0)
    sh.fill.solid(); sh.fill.fore_color.rgb=RGBColor.from_string(bg[1:]); sh.line.fill.background()
    y=y0+pad_top
    for i,(t,f) in enumerate(rows):
        lh=lh_t if f is ft else lh_b
        asc,desc=f.getmetrics(); base=y+(lh-(asc+desc))//2+asc
        size=fs_t if f is ft else int(fs_t*29/34)
        tb=sl.shapes.add_textbox(E(20*S),E(base-asc),E(bw-20*S+30),E(asc+desc)); tb.name=f'text{i+1}'
        tf=tb.text_frame; tf.word_wrap=True; tf.auto_size=MSO_AUTO_SIZE.NONE; tf.vertical_anchor=MSO_ANCHOR.TOP
        tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0
        tf.paragraphs[0].alignment=PP_ALIGN.LEFT
        r=tf.paragraphs[0].add_run(); r.text=t
        r.font.name='Bitter'; r.font.bold=(f is ft); r.font.size=Pt(size/ppx*72)
        r.font.color.rgb=RGBColor.from_string(fg[1:])
        y+=lh
    tmp=tempfile.mkdtemp(); stem=os.path.splitext(os.path.basename(out))[0]
    prs.save(f'{tmp}/{stem}.pptx')
    subprocess.run(['soffice','--headless','--convert-to','pdf','--outdir',tmp,f'{tmp}/{stem}.pptx'],capture_output=True,timeout=170)
    shutil.move(f'{tmp}/{stem}.pdf', os.path.splitext(out)[0]+'.pdf'); shutil.rmtree(tmp,ignore_errors=True)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('src');p.add_argument('out');p.add_argument('--title');p.add_argument('--dt');p.add_argument('--loc');p.add_argument('--key');p.add_argument('--cost');p.add_argument('--yoff',type=float,default=0.5);p.add_argument('--nowrap',action='store_true')
    a=p.parse_args(); build(a.src,a.out,a.title,a.dt,a.loc,a.key,a.cost,yoff=a.yoff,nowrap=a.nowrap)
