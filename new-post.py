#!/usr/bin/env python3
"""
Mystudionet Blog Post Generator
================================
Usage:
  python3 new-post.py post.txt      # Generate from input file
  python3 new-post.py               # Interactive mode (prompts)

After running:
  git add -A && git commit -m "Blog: <title>" && git push origin main
  Cloudflare deploys in ~2 minutes.

Input file format: see new-post-template.txt
"""

import sys, os, re, json
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
BLOG_DIR = os.path.join(BASE, 'blog')
POSTS_JSON = os.path.join(BLOG_DIR, 'posts.json')
SITEMAP = os.path.join(BASE, 'sitemap.xml')

SITE = 'https://mystudionet.com'

CATEGORIES = [
    'Video Production Tips',
    'Wedding Films',
    'AI & Technology',
    'Marketing & Advertising',
    'Long Island Business',
    'Behind the Scenes',
]

CATEGORY_SERVICES = {
    'Wedding Films': ('/services/wedding-films', 'View Wedding Film Packages'),
    'AI & Technology': ('/services/ai-production', 'Learn About AI Production'),
    'Marketing & Advertising': ('/marketing/', 'See Our Ad Management Services'),
    'Video Production Tips': ('/services', 'Explore Our Services'),
    'Long Island Business': ('/location/long-island', 'Video Production on Long Island'),
    'Behind the Scenes': ('/work', 'See Our Work'),
}

# ── HELPERS ────────────────────────────────────────────────────────────────

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text.strip())
    return re.sub(r'-+', '-', text)

def reading_time(text):
    words = len(re.findall(r'\w+', text))
    return max(1, round(words / 220))

def excerpt(body, length=160):
    plain = re.sub(r'##+ |(\*\*|__|\*|_)', '', body)
    plain = ' '.join(plain.split())
    return plain[:length].rsplit(' ', 1)[0] + '…' if len(plain) > length else plain

def inline_fmt(t):
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', t)
    t = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" style="color:#fff;text-decoration:underline;text-underline-offset:3px;">\1</a>', t)
    return t

def parse_content(body):
    html = []
    for block in re.split(r'\n{2,}', body.strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith('## '):
            h = block[3:].strip()
            html.append(f'<h2 class="serif" style="font-size:clamp(1.4rem,3vw,2rem);color:#fff;margin:2.5rem 0 1rem;line-height:1.25;">{h}</h2>')
        elif block.startswith('### '):
            h = block[4:].strip()
            html.append(f'<h3 style="font-size:1.1rem;color:#fff;margin:2rem 0 0.75rem;font-weight:600;letter-spacing:0.02em;">{h}</h3>')
        elif block.startswith(('- ', '* ')):
            items = [ln[2:].strip() for ln in block.split('\n') if ln.strip().startswith(('- ','* '))]
            lis = ''.join(f'<li style="color:#fff;font-size:1rem;line-height:1.8;margin-bottom:0.35rem;">{inline_fmt(i)}</li>' for i in items)
            html.append(f'<ul style="margin:0.5rem 0 1.5rem;padding-left:1.4rem;list-style:disc;">{lis}</ul>')
        elif block.startswith('IMG: '):
            parts = [x.strip() for x in block[5:].split('|')]
            fn = parts[0]
            alt = parts[1] if len(parts) > 1 else ''
            cap = parts[2] if len(parts) > 2 else ''
            cap_html = f'<div style="font-size:0.78rem;color:#fff;opacity:0.45;margin:-1.2rem 0 2.2rem;line-height:1.6;">{cap}</div>' if cap else ''
            html.append(f'<img src="/blog/images/{fn}" alt="{alt}" style="width:100%;margin:2rem 0;display:block;" loading="lazy">{cap_html}')
        elif block.startswith('VIDEO: '):
            raw_url = block[7:].strip()
            # Convert watch URL → embed URL for common platforms
            if 'youtube.com/watch' in raw_url:
                vid_id = re.search(r'v=([^&]+)', raw_url)
                embed_url = f'https://www.youtube.com/embed/{vid_id.group(1)}' if vid_id else raw_url
            elif 'youtu.be/' in raw_url:
                vid_id = raw_url.split('youtu.be/')[-1].split('?')[0]
                embed_url = f'https://www.youtube.com/embed/{vid_id}'
            elif 'vimeo.com/' in raw_url:
                vid_id = raw_url.rstrip('/').split('/')[-1]
                embed_url = f'https://player.vimeo.com/video/{vid_id}'
            elif 'adilo.com/watch/' in raw_url:
                vid_id = raw_url.split('/watch/')[-1].split('?')[0]
                embed_url = f'https://adilo.com/embed/{vid_id}'
            else:
                embed_url = raw_url
            html.append(f'<div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:2rem 0;"><iframe src="{embed_url}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:none;" allowfullscreen loading="lazy" title="Video"></iframe></div>')
        elif block.startswith(('1. ', '2. ')):
            items = [re.sub(r'^\d+\.\s+', '', ln).strip() for ln in block.split('\n') if re.match(r'^\d+\.', ln.strip())]
            lis = ''.join(f'<li style="color:#fff;font-size:1rem;line-height:1.8;margin-bottom:0.35rem;">{inline_fmt(i)}</li>' for i in items)
            html.append(f'<ol style="margin:0.5rem 0 1.5rem;padding-left:1.4rem;">{lis}</ol>')
        elif block.startswith('> '):
            q = block[2:].strip()
            html.append(f'<blockquote style="border-left:3px solid #fff;padding:1rem 1.5rem;margin:2rem 0;font-size:1.1rem;font-style:italic;color:#fff;font-family:\'Playfair Display\',serif;">{q}</blockquote>')
        else:
            p = block.replace('\n', ' ')
            p = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', p)
            p = re.sub(r'\*(.+?)\*', r'<em>\1</em>', p)
            p = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" style="color:#fff;text-decoration:underline;text-underline-offset:3px;">\1</a>', p)
            html.append(f'<p style="color:#fff;font-size:1rem;line-height:1.85;margin-bottom:1.4rem;">{p}</p>')
    return '\n'.join(html)

# ── NAV (shared across all pages) ─────────────────────────────────────────

NAV_HTML = '''  <nav id="nav" style="position:fixed;top:0;left:0;right:0;z-index:1000;padding:1.25rem 1.5rem;">
    <div style="max-width:1280px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;position:relative;">
      <a href="/" style="text-decoration:none;z-index:101;">
        <div class="serif" style="color:#000;font-size:1.1rem;letter-spacing:0.04em;">Mystudionet</div>
        <div style="font-size:0.6rem;letter-spacing:0.22em;text-transform:uppercase;color:#000;margin-top:1px;opacity:0.5;">Productions</div>
      </a>
      <div id="desk-nav" style="display:flex;align-items:center;gap:2rem;">
        <div class="nav-item">
          <a href="/work" class="nav-link">Work ▾</a>
          <div class="mega-panel">
            <div style="max-width:1280px;margin:0 auto;display:grid;grid-template-columns:1fr 1fr 1fr;gap:3rem;">
              <div>
                <div style="font-size:0.57rem;letter-spacing:0.22em;text-transform:uppercase;color:#888;margin-bottom:1rem;padding-bottom:0.6rem;border-bottom:1px solid #333;">Type of Video</div>
                <div style="display:flex;flex-direction:column;gap:0.3rem;">
                  <a href="/work/video-ad" class="mega-link">Video Ad</a><a href="/work/product-video" class="mega-link">Product Video</a><a href="/work/about-us-video" class="mega-link">About Us Video</a><a href="/work/testimonial-video" class="mega-link">Testimonial Video</a><a href="/work/event-video" class="mega-link">Event Video</a><a href="/work/explainer-video" class="mega-link">Explainer Video</a><a href="/work/tutorial-video" class="mega-link">Tutorial Video</a><a href="/work/team-video" class="mega-link">Team Video</a><a href="/work/ai-video" class="mega-link">AI Video</a><a href="/work/brand-film" class="mega-link">Brand Film</a><a href="/work/tv-commercial" class="mega-link">TV Commercial</a><a href="/work/real-estate-video" class="mega-link">Real Estate Video</a><a href="/work/wedding-film" class="mega-link">Wedding Film</a><a href="/work/social-media-reels" class="mega-link">Social Media / Reels</a><a href="/work/drone-video" class="mega-link">Drone Video</a><a href="/work/crowdfunding-video" class="mega-link">Crowdfunding Video</a>
                </div>
              </div>
              <div>
                <div style="font-size:0.57rem;letter-spacing:0.22em;text-transform:uppercase;color:#888;margin-bottom:1rem;padding-bottom:0.6rem;border-bottom:1px solid #333;">By Industry</div>
                <div style="display:flex;flex-direction:column;gap:0.3rem;">
                  <a href="/industry/software-tech" class="mega-link">Software &amp; Tech</a><a href="/industry/education" class="mega-link">Education</a><a href="/industry/retail-ecommerce" class="mega-link">Retail &amp; E-commerce</a><a href="/industry/beauty-fashion" class="mega-link">Beauty &amp; Fashion</a><a href="/industry/health-fitness" class="mega-link">Health &amp; Fitness</a><a href="/industry/food-restaurant" class="mega-link">Food &amp; Restaurant</a><a href="/industry/professional-services" class="mega-link">Professional Services</a><a href="/industry/home-garden" class="mega-link">Home &amp; Garden</a><a href="/industry/medical-biotech" class="mega-link">Medical &amp; Biotech</a><a href="/industry/travel-hospitality" class="mega-link">Travel &amp; Hospitality</a><a href="/industry/real-estate" class="mega-link">Real Estate</a><a href="/industry/media-entertainment" class="mega-link">Media &amp; Entertainment</a><a href="/industry/automotive" class="mega-link">Automotive</a><a href="/industry/nonprofit" class="mega-link">Nonprofit</a>
                </div>
              </div>
              <div>
                <div style="font-size:0.57rem;letter-spacing:0.22em;text-transform:uppercase;color:#888;margin-bottom:1rem;padding-bottom:0.6rem;border-bottom:1px solid #333;">By Location</div>
                <div style="display:flex;flex-direction:column;gap:0.3rem;">
                  <a href="/location/long-island" class="mega-link">Long Island</a><a href="/location/nyc" class="mega-link">New York City</a><a href="/location/hamptons" class="mega-link">The Hamptons</a><a href="/location/nassau-county" class="mega-link">Nassau County</a><a href="/location/suffolk-county" class="mega-link">Suffolk County</a><a href="/location/new-jersey" class="mega-link">New Jersey</a>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="nav-item">
          <a href="/services" class="nav-link">Services ▾</a>
          <div class="dropdown-panel">
            <a href="/services/ai-production" class="drop-link">AI-Powered Production</a><a href="/services/brand-commercial" class="drop-link">Brand &amp; Commercial</a><a href="/services/social-media" class="drop-link">Social Media Video</a><a href="/services/wedding-films" class="drop-link">Wedding Films</a>
          </div>
        </div>
        <div class="nav-item">
          <a href="/marketing/" class="nav-link">Marketing ▾</a>
          <div class="dropdown-panel">
            <a href="/marketing/meta-ads" class="drop-link">Meta Ads Management</a><a href="/marketing/google-ads" class="drop-link">Google Ads Management</a><a href="/marketing/youtube-ads" class="drop-link">YouTube Ad Management</a>
          </div>
        </div>
        <a href="/about" class="nav-link">About</a>
        <a href="/blog/" class="nav-link active">Blog</a>
        <a href="/contact" class="nav-link">Contact</a>
        <a href="/contact" style="display:inline-block;background:#fff;color:#000;font-size:0.65rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;padding:0.55rem 1.3rem;text-decoration:none;border:1px solid #fff;font-family:\'Poppins\',sans-serif;transition:background 0.2s,color 0.2s;" onmouseover="this.style.background=\'#000\';this.style.color=\'#fff\';" onmouseout="this.style.background=\'#fff\';this.style.color=\'#000\';">Start a Project</a>
      </div>
      <button id="mob-btn" onclick="toggleMob()" style="display:none;color:#000;background:none;border:none;cursor:pointer;">
        <svg width="22" height="14" viewBox="0 0 22 14" fill="none"><rect width="22" height="1.5" fill="currentColor"/><rect y="6" width="22" height="1.5" fill="currentColor"/><rect y="12" width="22" height="1.5" fill="currentColor"/></svg>
      </button>
    </div>
    <div id="mob-menu" style="display:none;position:fixed;inset:0;background:#000;z-index:1999;flex-direction:column;overflow:hidden;">
      <div style="display:flex;align-items:center;justify-content:space-between;padding:1.2rem 1.5rem;border-bottom:1px solid #111;flex-shrink:0;">
        <a href="/" style="text-decoration:none;"><div style="font-family:\'Playfair Display\',serif;color:#fff;font-size:1.05rem;letter-spacing:0.04em;">Mystudionet</div><div style="font-size:0.52rem;letter-spacing:0.22em;text-transform:uppercase;color:#fff;opacity:0.4;">Productions</div></a>
        <button onclick="toggleMob()" style="background:none;border:none;color:#fff;cursor:pointer;font-size:1.5rem;line-height:1;padding:0.4rem 0.6rem;">✕</button>
      </div>
      <div style="flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;">
        <div style="border-bottom:1px solid #111;"><button onclick="mobToggle(this)" style="width:100%;display:flex;justify-content:space-between;align-items:center;background:none;border:none;color:#fff;font-size:1.25rem;font-weight:500;font-family:\'Poppins\',sans-serif;padding:1rem 1.5rem;cursor:pointer;text-align:left;">Work <span class="mob-arr" style="color:#fff;opacity:0.4;font-size:1.1rem;">+</span></button>
          <div class="mob-sub" style="display:none;padding:0 1.5rem 1.25rem;">
            <div style="font-size:0.52rem;letter-spacing:0.2em;text-transform:uppercase;color:#fff;opacity:0.4;padding:0.25rem 0 0.6rem;">Type of Video</div>
            <a href="/work/video-ad" style="display:block;color:#fff;font-size:0.9rem;padding:0.45rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;border-bottom:1px solid #111;">Video Ad</a><a href="/work/product-video" style="display:block;color:#fff;font-size:0.9rem;padding:0.45rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;border-bottom:1px solid #111;">Product Video</a><a href="/work/brand-film" style="display:block;color:#fff;font-size:0.9rem;padding:0.45rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;border-bottom:1px solid #111;">Brand Film</a><a href="/work/wedding-film" style="display:block;color:#fff;font-size:0.9rem;padding:0.45rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;border-bottom:1px solid #111;">Wedding Film</a><a href="/work" style="display:block;color:#fff;font-size:0.9rem;padding:0.45rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;">→ View All Work</a>
          </div>
        </div>
        <div style="border-bottom:1px solid #111;"><button onclick="mobToggle(this)" style="width:100%;display:flex;justify-content:space-between;align-items:center;background:none;border:none;color:#fff;font-size:1.25rem;font-weight:500;font-family:\'Poppins\',sans-serif;padding:1rem 1.5rem;cursor:pointer;text-align:left;">Services <span class="mob-arr" style="color:#fff;opacity:0.4;font-size:1.1rem;">+</span></button>
          <div class="mob-sub" style="display:none;padding:0 1.5rem 1.25rem;">
            <a href="/services/ai-production" style="display:block;color:#fff;font-size:0.9rem;padding:0.55rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;border-bottom:1px solid #111;">AI-Powered Production</a><a href="/services/brand-commercial" style="display:block;color:#fff;font-size:0.9rem;padding:0.55rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;border-bottom:1px solid #111;">Brand &amp; Commercial</a><a href="/services/social-media" style="display:block;color:#fff;font-size:0.9rem;padding:0.55rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;border-bottom:1px solid #111;">Social Media Video</a><a href="/services/wedding-films" style="display:block;color:#fff;font-size:0.9rem;padding:0.55rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;">Wedding Films</a>
          </div>
        </div>
        <div style="border-bottom:1px solid #111;"><button onclick="mobToggle(this)" style="width:100%;display:flex;justify-content:space-between;align-items:center;background:none;border:none;color:#fff;font-size:1.25rem;font-weight:500;font-family:\'Poppins\',sans-serif;padding:1rem 1.5rem;cursor:pointer;text-align:left;">Marketing <span class="mob-arr" style="color:#fff;opacity:0.4;font-size:1.1rem;">+</span></button>
          <div class="mob-sub" style="display:none;padding:0 1.5rem 1.25rem;">
            <a href="/marketing/meta-ads" style="display:block;color:#fff;font-size:0.9rem;padding:0.55rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;border-bottom:1px solid #111;">Meta Ads Management</a><a href="/marketing/google-ads" style="display:block;color:#fff;font-size:0.9rem;padding:0.55rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;border-bottom:1px solid #111;">Google Ads Management</a><a href="/marketing/youtube-ads" style="display:block;color:#fff;font-size:0.9rem;padding:0.55rem 0;text-decoration:none;font-family:\'Poppins\',sans-serif;">YouTube Ad Management</a>
          </div>
        </div>
        <a href="/about" style="display:block;color:#fff;font-size:1.25rem;font-weight:500;font-family:\'Poppins\',sans-serif;padding:1rem 1.5rem;text-decoration:none;border-bottom:1px solid #111;">About</a>
        <a href="/blog/" style="display:block;color:#fff;font-size:1.25rem;font-weight:500;font-family:\'Poppins\',sans-serif;padding:1rem 1.5rem;text-decoration:none;border-bottom:1px solid #111;">Blog</a>
        <a href="/contact" style="display:block;color:#fff;font-size:1.25rem;font-weight:500;font-family:\'Poppins\',sans-serif;padding:1rem 1.5rem;text-decoration:none;border-bottom:1px solid #111;">Contact</a>
      </div>
      <div style="padding:1.25rem 1.5rem;flex-shrink:0;border-top:1px solid #111;">
        <a href="/contact" style="display:block;background:#fff;color:#000;text-align:center;padding:1rem;font-size:0.75rem;font-weight:600;letter-spacing:0.14em;text-transform:uppercase;text-decoration:none;font-family:\'Poppins\',sans-serif;">Start a Project →</a>
      </div>
    </div>
  </nav>'''

FOOTER_HTML = '''  <footer style="background:#000;border-top:1px solid #1a1a1a;padding:3rem 1.5rem;">
    <div style="max-width:1280px;margin:0 auto;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:2rem;">
      <div>
        <div style="font-family:\'Playfair Display\',serif;color:#fff;font-size:1rem;letter-spacing:0.04em;">Mystudionet</div>
        <div style="font-size:0.6rem;letter-spacing:0.22em;text-transform:uppercase;color:#fff;opacity:0.4;margin-top:2px;">Productions</div>
      </div>
      <p style="color:#fff;opacity:0.4;font-size:0.7rem;text-align:center;">© 2026 Mystudionet Productions · Long Island, NY</p>
      <div style="text-align:right;">
        <a href="tel:+16313555588" style="color:#fff;opacity:0.5;font-size:0.75rem;text-decoration:none;display:block;" onmouseover="this.style.opacity=\'1\'" onmouseout="this.style.opacity=\'0.5\'">(631) 355-5588</a>
        <a href="mailto:hello@mystudionet.com" style="color:#fff;opacity:0.5;font-size:0.75rem;text-decoration:none;display:block;margin-top:0.25rem;" onmouseover="this.style.opacity=\'1\'" onmouseout="this.style.opacity=\'0.5\'">hello@mystudionet.com</a>
      </div>
    </div>
  </footer>'''

SHARED_JS = '''  <script>
    window.addEventListener('scroll',function(){document.getElementById('nav').classList.toggle('scrolled',window.scrollY>60);});
    function toggleMob(){var m=document.getElementById('mob-menu');var open=m.style.display==='flex';m.style.display=open?'none':'flex';document.body.style.overflow=open?'':'hidden';}
    function mobToggle(btn){var sub=btn.nextElementSibling;var arr=btn.querySelector('.mob-arr');var isOpen=sub.style.display==='block';document.querySelectorAll('.mob-sub').forEach(function(s){s.style.display='none';});document.querySelectorAll('.mob-arr').forEach(function(a){a.textContent='+';});if(!isOpen){sub.style.display='block';if(arr)arr.textContent='−';}}
    (function(){var btn=document.getElementById('mob-btn');var nav=document.getElementById('desk-nav');function chk(){if(window.innerWidth<900){btn.style.display='block';nav.style.display='none';}else{btn.style.display='none';nav.style.display='flex';var m=document.getElementById('mob-menu');if(m){m.style.display='none';document.body.style.overflow='';}}}chk();window.addEventListener('resize',chk);})();
    (function(){var T={};document.querySelectorAll('.nav-item').forEach(function(item,i){item.addEventListener('mouseenter',function(){clearTimeout(T[i]);item.classList.add('open');});item.addEventListener('mouseleave',function(){T[i]=setTimeout(function(){item.classList.remove('open');},220);});var p=item.querySelector('.mega-panel,.dropdown-panel');if(p){p.addEventListener('mouseenter',function(){clearTimeout(T[i]);});p.addEventListener('mouseleave',function(){T[i]=setTimeout(function(){item.classList.remove('open');},220);});}});})();
    var obs=new IntersectionObserver(function(e){e.forEach(function(x){if(x.isIntersecting){x.target.classList.add('visible');obs.unobserve(x.target);}});},{threshold:0.08});
    document.querySelectorAll('.reveal').forEach(function(el){obs.observe(el);});
  </script>'''

SHARED_CSS = '''    *, *::before, *::after { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body { background: #000; color: #fff; font-family: 'Poppins', sans-serif; -webkit-font-smoothing: antialiased; }
    .serif { font-family: 'Playfair Display', Georgia, serif; }
    #nav { background: #fff; border-bottom: 1px solid #e8e8e8; transition: background 0.3s, border-color 0.3s, box-shadow 0.3s; }
    #nav.scrolled { background: #fff; border-bottom: 1px solid #ddd; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }
    .reveal { opacity: 0; transform: translateY(18px); transition: opacity 0.6s ease, transform 0.6s ease; }
    .reveal.visible { opacity: 1; transform: translateY(0); }
    ::-webkit-scrollbar { width: 3px; } ::-webkit-scrollbar-track { background: #000; } ::-webkit-scrollbar-thumb { background: #fff; }
    .nav-link{color:#000;font-size:0.65rem;letter-spacing:0.18em;text-transform:uppercase;text-decoration:none;font-family:'Poppins',sans-serif;transition:opacity 0.2s;white-space:nowrap;}
    .nav-link:hover,.nav-link.active{opacity:0.65;}
    .mega-link{color:#222;font-size:0.875rem;text-decoration:none;font-family:'Poppins',sans-serif;padding:0.3rem 0;transition:opacity 0.2s;display:block;}
    .mega-link:hover{opacity:0.6;}
    .drop-link{color:#000;font-size:0.875rem;text-decoration:none;font-family:'Poppins',sans-serif;padding:0.75rem 1.25rem;display:block;transition:background 0.15s;white-space:nowrap;}
    .drop-link:hover{background:#f5f5f5;}
    .nav-item{position:relative;}
    .mega-panel{display:none;position:fixed;left:0;right:0;top:62px;background:#fff;border-top:1px solid #e8e8e8;border-bottom:1px solid #e8e8e8;padding:2rem 1.5rem;z-index:998;box-shadow:0 8px 24px rgba(0,0,0,0.08);}
    .nav-item.open .mega-panel{display:block;}
    .dropdown-panel{display:none;position:absolute;top:calc(100% + 0.4rem);left:50%;transform:translateX(-50%);background:#fff;border:1px solid #e8e8e8;min-width:220px;z-index:998;padding:0.5rem 0;box-shadow:0 4px 16px rgba(0,0,0,0.1);}
    .nav-item.open .dropdown-panel{display:block;}
    [style*="background:#fff"] h1,[style*="background:#fff"] h2,[style*="background:#fff"] h3,
    [style*="background:#fff"] h4,[style*="background:#fff"] p,[style*="background:#fff"] span,
    [style*="background:#fff"] li,[style*="background:#fff"] label,[style*="background:#fff"] div{color:#111 !important;}
    [style*="background:#fff"] a:not([style*="background:#000"]):not(.btn-primary){color:#111 !important;}'''

# ── POST PAGE GENERATOR ────────────────────────────────────────────────────

def related_posts_html(current_slug, current_category, posts, max_count=3):
    """Return up to max_count related post cards (same category first)."""
    others = [p for p in posts if p['slug'] != current_slug]
    same_cat = [p for p in others if p['category'] == current_category]
    diff_cat = [p for p in others if p['category'] != current_category]
    picked = (same_cat + diff_cat)[:max_count]
    if not picked:
        return ''
    cards = []
    for p in picked:
        date_fmt = datetime.strptime(p['date'], '%Y-%m-%d').strftime('%b %d, %Y')
        img_html = f'<img src="/blog/images/{p["image"]}" alt="{p["title"]}" style="width:100%;height:100%;object-fit:cover;display:block;">' if p.get('image') else '<div style="background:#111;width:100%;height:100%;"></div>'
        cards.append(f'''      <a href="/blog/{p['slug']}" style="text-decoration:none;display:block;border:1px solid #1a1a1a;transition:border-color 0.25s;" onmouseover="this.style.borderColor=\'#555\'" onmouseout="this.style.borderColor=\'#1a1a1a\'">
        <div style="height:160px;overflow:hidden;">{img_html}</div>
        <div style="padding:1.25rem;">
          <div style="font-size:0.55rem;letter-spacing:0.16em;text-transform:uppercase;color:#fff;opacity:0.4;margin-bottom:0.5rem;">{p['category']} · {date_fmt}</div>
          <h3 class="serif" style="font-size:1rem;color:#fff;line-height:1.35;margin-bottom:0.5rem;">{p['title']}</h3>
          <p style="font-size:0.8rem;color:#fff;opacity:0.6;line-height:1.55;">{p['excerpt'][:100]}…</p>
        </div>
      </a>''')
    cards_html = '\n'.join(cards)
    return f'''  <section style="background:#000;padding:3rem 1.5rem 5rem;border-top:1px solid #1a1a1a;">
    <div style="max-width:1280px;margin:0 auto;">
      <div style="font-size:0.6rem;letter-spacing:0.22em;text-transform:uppercase;color:#fff;opacity:0.4;margin-bottom:2rem;">You Might Also Like</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1.25rem;">
{cards_html}
      </div>
    </div>
  </section>'''

def generate_post_html(meta, content_html, related=[]):
    title    = meta['title']
    desc     = meta['description']
    slug     = meta['slug']
    category = meta['category']
    date_iso = meta['date']
    date_fmt = datetime.strptime(date_iso, '%Y-%m-%d').strftime('%B %d, %Y')
    image    = meta.get('image', '')
    tags     = meta.get('tags', [])
    rt       = meta.get('reading_time', 5)
    raw_body = meta.get('_raw_body', '')

    related_section = related_posts_html(slug, category, related) if related else ''

    img_url  = f'{SITE}/blog/images/{image}' if image else f'{SITE}/og-image.jpg'
    img_tag  = f'<img src="/blog/images/{image}" alt="{title}" style="width:100%;height:100%;object-fit:cover;display:block;">' if image else ''

    svc_link, svc_label = CATEGORY_SERVICES.get(category, ('/services', 'Explore Our Services'))

    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": desc,
        "image": img_url,
        "datePublished": date_iso,
        "dateModified": date_iso,
        "author": {"@type": "Person", "name": "Kursad Yonet", "url": f"{SITE}/about"},
        "publisher": {
            "@type": "Organization",
            "name": "Mystudionet Productions",
            "logo": {"@type": "ImageObject", "url": f"{SITE}/favicon.png"}
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"{SITE}/blog/{slug}"},
        "keywords": ", ".join(tags),
        "articleSection": category,
        "wordCount": len(re.findall(r'\w+', raw_body))
    }, indent=2)

    breadcrumb_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": f"{SITE}/blog/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": f"{SITE}/blog/{slug}"}
        ]
    })

    tag_links = ' '.join(
        '<a href="/blog/?tag=' + t.strip().lower().replace(' ', '-') + '" class="tag-chip">' + t.strip() + '</a>'
        for t in tags
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | Mystudionet Productions Blog</title>
  <meta name="description" content="{desc}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{SITE}/blog/{slug}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{SITE}/blog/{slug}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:image" content="{img_url}">
  <meta property="og:site_name" content="Mystudionet Productions">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{desc}">
  <meta name="twitter:image" content="{img_url}">
  <meta name="article:published_time" content="{date_iso}">
  <meta name="article:section" content="{category}">
  {''.join(f'<meta name="article:tag" content="{t.strip()}">' for t in tags)}
  <link rel="icon" type="image/png" href="/favicon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,700;1,400&family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">
  <script type="application/ld+json">{json_ld}</script>
  <script type="application/ld+json">{breadcrumb_ld}</script>
  <style>
{SHARED_CSS}
    .prose a {{ color:#fff; text-decoration:underline; text-underline-offset:3px; }}
    .prose a:hover {{ opacity:0.7; }}
    .tag-chip {{ display:inline-block; border:1px solid #333; color:#fff; font-size:0.65rem; letter-spacing:0.12em; text-transform:uppercase; padding:0.3rem 0.75rem; text-decoration:none; font-family:'Poppins',sans-serif; transition:border-color 0.2s; margin:0.2rem; }}
    .tag-chip:hover {{ border-color:#fff; }}
    .share-btn {{ display:inline-flex; align-items:center; gap:0.5rem; border:1px solid #333; color:#fff; font-size:0.65rem; letter-spacing:0.12em; text-transform:uppercase; padding:0.55rem 1rem; text-decoration:none; font-family:'Poppins',sans-serif; transition:border-color 0.2s,background 0.2s; }}
    .share-btn:hover {{ border-color:#fff; background:#111; }}
    @media(max-width:800px){
      [style*="grid-template-columns"]{grid-template-columns:1fr !important;gap:2.5rem !important;}
    }
  </style>
  <!-- Google Analytics -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-RG3RKR89SM"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-RG3RKR89SM');
  </script>
</head>
<body>

{NAV_HTML}

  <!-- HERO -->
  <section style="background:#000;padding-top:6rem;">
    {'<div style="max-width:900px;margin:0 auto;padding:0 1.5rem 0;">' if not image else f'<div style="width:100%;max-height:480px;overflow:hidden;margin-bottom:0;">{img_tag}</div><div style="max-width:900px;margin:0 auto;padding:0 1.5rem;">'}
    <div style="padding-top:3rem;padding-bottom:0.5rem;">
      <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap;">
        <a href="/blog/" style="font-size:0.6rem;letter-spacing:0.2em;text-transform:uppercase;color:#fff;text-decoration:none;opacity:0.5;" onmouseover="this.style.opacity=\'1\'" onmouseout="this.style.opacity=\'0.5\'">← Blog</a>
        <span style="color:#333;">·</span>
        <span style="font-size:0.6rem;letter-spacing:0.18em;text-transform:uppercase;color:#fff;opacity:0.5;">{category}</span>
        <span style="color:#333;">·</span>
        <span style="font-size:0.6rem;letter-spacing:0.18em;text-transform:uppercase;color:#fff;opacity:0.5;">{rt} min read</span>
      </div>
      <h1 class="serif" style="font-size:clamp(2rem,5vw,3.5rem);color:#fff;line-height:1.15;margin-bottom:1.5rem;">{title}</h1>
      <p style="font-size:1rem;color:#fff;opacity:0.6;line-height:1.7;max-width:640px;margin-bottom:2rem;">{desc}</p>
      <div style="display:flex;align-items:center;gap:1rem;padding-bottom:2.5rem;border-bottom:1px solid #1a1a1a;">
        <div>
          <div style="font-size:0.8rem;font-weight:500;color:#fff;">Kursad Yonet</div>
          <div style="font-size:0.7rem;color:#fff;opacity:0.5;">{date_fmt}</div>
        </div>
      </div>
    </div>
    </div>
  </section>

  <!-- ARTICLE BODY -->
  <section style="background:#000;padding:4rem 1.5rem 5rem;">
    <div style="max-width:720px;margin:0 auto;" class="prose">
{content_html}
    </div>
  </section>

  <!-- TAGS -->
  {'<section style="background:#000;padding:0 1.5rem 3rem;border-bottom:1px solid #1a1a1a;"><div style="max-width:720px;margin:0 auto;"><div style="font-size:0.6rem;letter-spacing:0.2em;text-transform:uppercase;color:#fff;opacity:0.4;margin-bottom:1rem;">Tags</div><div>' + tag_links + '</div></div></section>' if tags else ''}

  <!-- SHARE -->
  <section style="background:#000;padding:3rem 1.5rem;">
    <div style="max-width:720px;margin:0 auto;">
      <div style="font-size:0.6rem;letter-spacing:0.2em;text-transform:uppercase;color:#fff;opacity:0.4;margin-bottom:1rem;">Share This Article</div>
      <div style="display:flex;gap:0.75rem;flex-wrap:wrap;">
        <a href="https://twitter.com/intent/tweet?url={SITE}/blog/{slug}&text={title.replace(' ', '%20')}" target="_blank" rel="noopener" class="share-btn">Twitter / X</a>
        <a href="https://www.linkedin.com/shareArticle?mini=true&url={SITE}/blog/{slug}&title={title.replace(' ', '%20')}" target="_blank" rel="noopener" class="share-btn">LinkedIn</a>
        <a href="https://www.facebook.com/sharer/sharer.php?u={SITE}/blog/{slug}" target="_blank" rel="noopener" class="share-btn">Facebook</a>
      </div>
    </div>
  </section>

  <!-- AUTHOR -->
  <section style="background:#111;padding:3rem 1.5rem;">
    <div style="max-width:720px;margin:0 auto;display:flex;gap:2rem;align-items:flex-start;">
      <img src="/kursad.jpg" alt="Kursad Yonet" style="width:72px;height:72px;object-fit:cover;flex-shrink:0;filter:grayscale(100%);">
      <div>
        <div style="font-size:0.6rem;letter-spacing:0.2em;text-transform:uppercase;color:#fff;opacity:0.4;margin-bottom:0.5rem;">Written by</div>
        <div style="font-size:1rem;font-weight:600;color:#fff;margin-bottom:0.5rem;">Kursad Yonet</div>
        <p style="font-size:0.875rem;color:#fff;opacity:0.7;line-height:1.7;margin-bottom:1rem;">Founder of Mystudionet Productions. 20+ years of cinematic storytelling, now supercharged with AI. Based on Long Island, NY.</p>
        <a href="/about" style="font-size:0.65rem;letter-spacing:0.14em;text-transform:uppercase;color:#fff;text-decoration:none;border-bottom:1px solid #555;padding-bottom:2px;">About Kursad →</a>
      </div>
    </div>
  </section>

{related_section}

  <!-- CTA -->
  <section style="background:#fff;padding:5rem 1.5rem;text-align:center;">
    <div style="max-width:640px;margin:0 auto;">
      <div style="font-size:0.6rem;letter-spacing:0.22em;text-transform:uppercase;color:#000;margin-bottom:1.5rem;">{category}</div>
      <h2 class="serif" style="font-size:clamp(1.8rem,4vw,2.8rem);color:#000;margin-bottom:1.25rem;line-height:1.2;">Ready to Start Your Project?</h2>
      <p style="font-size:0.95rem;color:#000;margin-bottom:2.5rem;line-height:1.7;">Free discovery call. No commitment.</p>
      <div style="display:flex;gap:1rem;justify-content:center;flex-wrap:wrap;">
        <a href="/contact" style="display:inline-block;background:#000;color:#fff;font-size:0.72rem;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;padding:0.9rem 2.2rem;text-decoration:none;border:1px solid #000;transition:background 0.2s,color 0.2s;" onmouseover="this.style.background=\'#fff\';this.style.color=\'#000\';" onmouseout="this.style.background=\'#000\';this.style.color=\'#fff\';">Book a Free Call</a>
        <a href="{svc_link}" style="display:inline-block;background:transparent;color:#000;font-size:0.72rem;font-weight:500;letter-spacing:0.12em;text-transform:uppercase;padding:0.9rem 2.2rem;text-decoration:none;border:1px solid #bbb;transition:border-color 0.2s;" onmouseover="this.style.borderColor=\'#000\'" onmouseout="this.style.borderColor=\'#bbb\'">{svc_label}</a>
      </div>
    </div>
  </section>

{FOOTER_HTML}

{SHARED_JS}
</body>
</html>'''

# ── BLOG INDEX PAGE ────────────────────────────────────────────────────────

def build_index(posts):
    """Rebuild /blog/index.html from posts list (newest first)."""
    posts_sorted = sorted(posts, key=lambda p: p['date'], reverse=True)

    cards = []
    for p in posts_sorted:
        date_fmt = datetime.strptime(p['date'], '%Y-%m-%d').strftime('%b %d, %Y')
        img_html = f'<img src="/blog/images/{p["image"]}" alt="{p["title"]}" style="width:100%;height:100%;object-fit:cover;display:block;transition:transform 0.5s ease;">' if p.get('image') else '<div style="background:#111;width:100%;height:100%;display:flex;align-items:center;justify-content:center;"><span style="color:#333;font-size:0.7rem;letter-spacing:0.1em;">NO IMAGE</span></div>'
        cards.append(f'''        <a href="/blog/{p['slug']}" style="text-decoration:none;display:block;border:1px solid #1a1a1a;transition:border-color 0.25s;" onmouseover="this.style.borderColor=\'#555\';this.querySelector(\'img\')&&(this.querySelector(\'img\').style.transform=\'scale(1.04)\')" onmouseout="this.style.borderColor=\'#1a1a1a\';this.querySelector(\'img\')&&(this.querySelector(\'img\').style.transform=\'scale(1)\')">
          <div style="height:220px;overflow:hidden;">{img_html}</div>
          <div style="padding:1.5rem;">
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.75rem;">
              <span style="font-size:0.55rem;letter-spacing:0.18em;text-transform:uppercase;color:#fff;opacity:0.5;">{p['category']}</span>
              <span style="color:#333;">·</span>
              <span style="font-size:0.55rem;letter-spacing:0.12em;text-transform:uppercase;color:#fff;opacity:0.5;">{p.get('reading_time',5)} min read</span>
            </div>
            <h2 class="serif" style="font-size:1.2rem;color:#fff;line-height:1.3;margin-bottom:0.75rem;">{p['title']}</h2>
            <p style="font-size:0.85rem;color:#fff;opacity:0.6;line-height:1.6;margin-bottom:1.25rem;">{p['excerpt']}</p>
            <div style="font-size:0.65rem;letter-spacing:0.14em;text-transform:uppercase;color:#fff;opacity:0.5;">{date_fmt}</div>
          </div>
        </a>''')

    cards_html = '\n'.join(cards) if cards else '<p style="color:#fff;opacity:0.5;text-align:center;padding:4rem 0;">No posts yet.</p>'
    count = len(posts_sorted)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Blog | Mystudionet Productions — Video Production Insights</title>
  <meta name="description" content="Video production tips, AI filmmaking insights, wedding film advice, and marketing strategies from Mystudionet Productions on Long Island, NY.">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{SITE}/blog/">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{SITE}/blog/">
  <meta property="og:title" content="Blog | Mystudionet Productions">
  <meta property="og:description" content="Video production tips, AI filmmaking insights, and marketing strategies from Long Island's AI-powered studio.">
  <meta property="og:image" content="{SITE}/og-image.jpg">
  <link rel="icon" type="image/png" href="/favicon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,700;1,400&family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">
  <script type="application/ld+json">{json.dumps({"@context":"https://schema.org","@type":"Blog","name":"Mystudionet Productions Blog","url":f"{SITE}/blog/","description":"Video production insights from Long Island's AI-powered studio."})}</script>
  <style>
{SHARED_CSS}
  </style>
</head>
<body>

{NAV_HTML}

  <!-- HEADER -->
  <section style="background:#000;padding:9rem 1.5rem 5rem;text-align:center;">
    <div style="max-width:700px;margin:0 auto;">
      <div style="font-size:0.6rem;letter-spacing:0.22em;text-transform:uppercase;color:#fff;opacity:0.4;margin-bottom:1.5rem;">Insights &amp; Education</div>
      <h1 class="serif" style="font-size:clamp(2.5rem,6vw,4rem);color:#fff;line-height:1.1;margin-bottom:1.5rem;">The Blog</h1>
      <p style="font-size:1rem;color:#fff;opacity:0.6;line-height:1.7;">Video production tips, AI filmmaking, wedding film advice, and marketing insights from Long Island&rsquo;s AI-powered studio.</p>
    </div>
  </section>

  <!-- POST GRID -->
  <section style="background:#000;padding:2rem 1.5rem 6rem;">
    <div style="max-width:1280px;margin:0 auto;">
      <div style="font-size:0.6rem;letter-spacing:0.2em;text-transform:uppercase;color:#fff;opacity:0.35;margin-bottom:2rem;">{count} article{'s' if count!=1 else ''}</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:1.5rem;">
{cards_html}
      </div>
    </div>
  </section>

{FOOTER_HTML}

{SHARED_JS}
</body>
</html>'''

# ── SITEMAP ────────────────────────────────────────────────────────────────

def update_sitemap(slug, date_iso):
    url = f'{SITE}/blog/{slug}'
    if os.path.exists(SITEMAP):
        with open(SITEMAP, 'r') as f:
            content = f.read()
        if url in content:
            return
        entry = f'\n  <url>\n    <loc>{url}</loc>\n    <lastmod>{date_iso}</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>'
        content = content.replace('</urlset>', entry + '\n</urlset>')
        with open(SITEMAP, 'w') as f:
            f.write(content)
    else:
        # Create minimal sitemap
        content = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{SITE}/</loc><priority>1.0</priority></url>
  <url><loc>{SITE}/blog/</loc><priority>0.9</priority></url>
  <url>
    <loc>{url}</loc>
    <lastmod>{date_iso}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>'''
        with open(SITEMAP, 'w') as f:
            f.write(content)
    print(f'  ✓ sitemap.xml updated')

# ── PARSE INPUT FILE ───────────────────────────────────────────────────────

def parse_input_file(filepath):
    with open(filepath, 'r') as f:
        raw = f.read()

    parts = raw.split('\n---\n', 1)
    if len(parts) != 2:
        print('ERROR: Input file must have "---" separator between headers and body.')
        sys.exit(1)

    header_block, body = parts
    meta = {}

    for line in header_block.strip().split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            meta[key.strip().upper()] = val.strip()

    title = meta.get('TITLE', '')
    if not title:
        print('ERROR: TITLE is required.')
        sys.exit(1)

    tags_raw = meta.get('TAGS', '')
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()] if tags_raw else []

    slug = meta.get('SLUG', '') or slugify(title)
    date_iso = meta.get('DATE', datetime.today().strftime('%Y-%m-%d'))
    rt = reading_time(body)
    ex = excerpt(body)

    return {
        'title':        title,
        'slug':         slug,
        'description':  meta.get('DESCRIPTION', ex),
        'category':     meta.get('CATEGORY', 'Video Production Tips'),
        'image':        meta.get('IMAGE', ''),
        'tags':         tags,
        'date':         date_iso,
        'reading_time': rt,
        'excerpt':      ex,
        '_raw_body':    body,
    }, body.strip()

def interactive_mode():
    print('\n── Mystudionet Blog Post Generator ──\n')
    title = input('Post Title: ').strip()
    slug_suggest = slugify(title)
    slug_in = input(f'URL Slug [{slug_suggest}]: ').strip()
    slug = slug_in or slug_suggest

    desc = input('Meta Description (150-155 chars): ').strip()

    print(f'\nCategories:')
    for i, c in enumerate(CATEGORIES, 1):
        print(f'  {i}. {c}')
    cat_idx = input('Category number [1]: ').strip()
    category = CATEGORIES[int(cat_idx)-1] if cat_idx.isdigit() and 1 <= int(cat_idx) <= len(CATEGORIES) else CATEGORIES[0]

    image = input('Cover image filename (place in blog/images/): ').strip()
    tags_raw = input('Tags (comma-separated): ').strip()
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
    date_iso = datetime.today().strftime('%Y-%m-%d')

    print('\nPaste article body (end with a line containing only "END"):')
    lines = []
    while True:
        line = input()
        if line.strip() == 'END':
            break
        lines.append(line)
    body = '\n'.join(lines)

    rt = reading_time(body)
    ex = excerpt(body)

    meta = {
        'title': title, 'slug': slug,
        'description': desc or ex, 'category': category,
        'image': image, 'tags': tags,
        'date': date_iso, 'reading_time': rt,
        'excerpt': ex, '_raw_body': body,
    }
    return meta, body.strip()

# ── MAIN ───────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if not os.path.exists(filepath):
            print(f'ERROR: File not found: {filepath}')
            sys.exit(1)
        meta, body = parse_input_file(filepath)
    else:
        meta, body = interactive_mode()

    slug = meta['slug']
    content_html = parse_content(body)

    # Load existing posts for "You might also like"
    existing_posts = []
    if os.path.exists(POSTS_JSON):
        with open(POSTS_JSON, 'r') as f:
            existing_posts = json.load(f)

    # 1. Write post HTML
    post_path = os.path.join(BLOG_DIR, f'{slug}.html')
    post_html = generate_post_html(meta, content_html, related=existing_posts)
    with open(post_path, 'w') as f:
        f.write(post_html)
    print(f'\n  ✓ Blog post: blog/{slug}.html')

    # 2. Update posts.json
    posts = []
    if os.path.exists(POSTS_JSON):
        with open(POSTS_JSON, 'r') as f:
            posts = json.load(f)
    # Remove existing entry with same slug (update)
    posts = [p for p in posts if p.get('slug') != slug]
    posts.append({
        'title':        meta['title'],
        'slug':         slug,
        'description':  meta['description'],
        'category':     meta['category'],
        'image':        meta.get('image', ''),
        'tags':         meta.get('tags', []),
        'date':         meta['date'],
        'reading_time': meta['reading_time'],
        'excerpt':      meta['excerpt'],
    })
    with open(POSTS_JSON, 'w') as f:
        json.dump(posts, f, indent=2)
    print(f'  ✓ posts.json updated ({len(posts)} posts)')

    # 3. Rebuild blog index
    index_html = build_index(posts)
    with open(os.path.join(BLOG_DIR, 'index.html'), 'w') as f:
        f.write(index_html)
    print(f'  ✓ blog/index.html rebuilt')

    # 4. Update sitemap
    update_sitemap(slug, meta['date'])

    # 5. Summary
    print(f'''
── Done! ────────────────────────────────
  URL:       {SITE}/blog/{slug}
  Title:     {meta['title']}
  Category:  {meta['category']}
  Read time: {meta['reading_time']} min
  Date:      {meta['date']}

Next step — publish:
  git add -A && git commit -m "Blog: {meta['title']}" && git push origin main
─────────────────────────────────────────
''')

if __name__ == '__main__':
    main()
