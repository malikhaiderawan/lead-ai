#!/usr/bin/env python3
"""Generates the official MalikAxiom Master Reels & Video Content Playbook PDF.

Output: output/MalikAxiom_Master_Reels_Playbook.pdf
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PAGE_WIDTH = 595.28   # A4 width
PAGE_HEIGHT = 841.89  # A4 height
MARGIN_LEFT = 38
MARGIN_RIGHT = 557
CONTENT_WIDTH = MARGIN_RIGHT - MARGIN_LEFT
TOP_Y = 792
BOTTOM_Y = 48


class ReelsPSWriter:
    def __init__(self):
        self.pages: list[list[str]] = [[]]
        self.current_y = TOP_Y
        self.page_num = 1

    def _cur(self) -> list[str]:
        return self.pages[-1]

    def new_page(self):
        self.pages.append([])
        self.page_num += 1
        self.current_y = TOP_Y

    def ensure_space(self, needed_pt: float):
        if self.current_y - needed_pt < BOTTOM_Y:
            self.new_page()

    def add_raw(self, ps_code: str):
        self._cur().append(ps_code)

    def draw_header_footer(self, page_idx: int, total_pages: int):
        lines = []
        if page_idx > 1:
            lines.append(f"""
            gsave
            0.85 0.88 0.92 setrgbcolor
            {MARGIN_LEFT} 812 moveto {MARGIN_RIGHT} 812 lineto stroke
            /Helvetica-Bold findfont 8 scalefont setfont
            0.106 0.212 0.365 setrgbcolor
            {MARGIN_LEFT} 817 moveto (MALIKAXIOM TECHNOLOGY  |  VIRAL REELS & CONTENT PLAYBOOK) show
            /Helvetica findfont 8 scalefont setfont
            0.45 0.50 0.55 setrgbcolor
            430 817 moveto (FASHION & BUSINESS DIGITALIZATION) show
            grestore
            """)

        lines.append(f"""
        gsave
        0.85 0.88 0.92 setrgbcolor
        {MARGIN_LEFT} 36 moveto {MARGIN_RIGHT} 36 lineto stroke
        /Helvetica findfont 8 scalefont setfont
        0.45 0.50 0.55 setrgbcolor
        {MARGIN_LEFT} 25 moveto (MalikAxiom Technology - https://malikaxiomtech.com - WhatsApp: +92 313 0466400) show
        /Helvetica-Bold findfont 8 scalefont setfont
        0.106 0.212 0.365 setrgbcolor
        510 25 moveto (Page {page_idx} of {total_pages}) show
        grestore
        """)
        return "\n".join(lines)

    def draw_header_banner(self, title: str, subtitle: str, badge: str):
        self.ensure_space(105)
        y = self.current_y
        ps = f"""
        gsave
        0.106 0.212 0.365 setrgbcolor
        {MARGIN_LEFT} {y - 68} {CONTENT_WIDTH} 74 rectfill
        
        0.90 0.45 0.10 setrgbcolor
        {MARGIN_LEFT} {y - 71} {CONTENT_WIDTH} 3 rectfill
        
        1.0 1.0 1.0 setrgbcolor
        /Helvetica-Bold findfont 14 scalefont setfont
        {MARGIN_LEFT + 14} {y - 20} moveto ({self._esc(title)}) show
        
        0.92 0.75 0.40 setrgbcolor
        /Helvetica-Bold findfont 9.5 scalefont setfont
        {MARGIN_LEFT + 14} {y - 38} moveto ({self._esc(subtitle)}) show
        
        0.85 0.90 0.95 setrgbcolor
        /Helvetica findfont 8.0 scalefont setfont
        {MARGIN_LEFT + 14} {y - 56} moveto ({self._esc(badge)}) show
        grestore
        """
        self.add_raw(ps)
        self.current_y -= 84

    def draw_section_heading(self, text: str, color=(0.106, 0.212, 0.365)):
        self.ensure_space(34)
        self.current_y -= 5
        y = self.current_y
        r, g, b = color
        ps = f"""
        gsave
        {r} {g} {b} setrgbcolor
        {MARGIN_LEFT} {y - 14} 3.5 14 rectfill
        
        /Helvetica-Bold findfont 10.5 scalefont setfont
        {MARGIN_LEFT + 9} {y - 11} moveto ({self._esc(text)}) show
        
        0.85 0.88 0.92 setrgbcolor
        {MARGIN_LEFT + 9} {y - 16} moveto {MARGIN_RIGHT} {y - 16} lineto stroke
        grestore
        """
        self.add_raw(ps)
        self.current_y -= 22

    def draw_reel_card(self, number: int, title: str, target: str, duration: str, angle: str,
                       hook: str, pain: str, solution: str, offer: str, cta: str,
                       accent_color=(0.106, 0.212, 0.365)):
        # Measure wrapped text lines for each section
        h_lines = self._wrap_text(hook, 7.8, CONTENT_WIDTH - 24)
        p_lines = self._wrap_text(pain, 7.8, CONTENT_WIDTH - 24)
        s_lines = self._wrap_text(solution, 7.8, CONTENT_WIDTH - 24)
        o_lines = self._wrap_text(offer, 7.8, CONTENT_WIDTH - 24)
        c_lines = self._wrap_text(cta, 7.8, CONTENT_WIDTH - 24)

        card_h = (
            24 + 14 +
            (len(h_lines) * 10.5 + 12) +
            (len(p_lines) * 10.5 + 12) +
            (len(s_lines) * 10.5 + 12) +
            (len(o_lines) * 10.5 + 12) +
            (len(c_lines) * 10.5 + 12)
        )
        self.ensure_space(card_h + 10)
        self.current_y -= 4
        y = self.current_y
        ar, ag, ab = accent_color

        # Outer box
        ps = f"""
        gsave
        0.98 0.985 0.995 setrgbcolor
        {MARGIN_LEFT} {y - card_h} {CONTENT_WIDTH} {card_h} rectfill
        0.84 0.87 0.91 setrgbcolor
        {MARGIN_LEFT} {y - card_h} {CONTENT_WIDTH} {card_h} rectstroke
        {ar} {ag} {ab} setrgbcolor
        {MARGIN_LEFT} {y - card_h} 3.5 {card_h} rectfill
        
        % Card Title Bar
        /Helvetica-Bold findfont 9.0 scalefont setfont
        {ar} {ag} {ab} setrgbcolor
        {MARGIN_LEFT + 10} {y - 12} moveto ({self._esc(f"REEL {number}: {title}")}) show
        
        /Helvetica-Bold findfont 7.8 scalefont setfont
        0.85 0.40 0.05 setrgbcolor
        460 {y - 12} moveto ({self._esc(f"[{duration}]")}) show
        
        /Helvetica findfont 7.5 scalefont setfont
        0.40 0.45 0.50 setrgbcolor
        {MARGIN_LEFT + 10} {y - 23} moveto ({self._esc(f"Target: {target}  |  Angle: {angle}")}) show
        grestore
        """
        self.add_raw(ps)

        cur_y = y - 35

        def _draw_block(label: str, lines: list[str], lbl_color=(0.106, 0.212, 0.365)):
            nonlocal cur_y
            lr, lg, lb = lbl_color
            ps_lbl = f"""
            gsave
            {lr} {lg} {lb} setrgbcolor
            /Helvetica-Bold findfont 7.5 scalefont setfont
            {MARGIN_LEFT + 10} {cur_y} moveto ({self._esc(label)}) show
            grestore
            """
            self.add_raw(ps_lbl)
            cur_y -= 10
            for l in lines:
                ps_t = f"""
                gsave
                0.15 0.18 0.22 setrgbcolor
                /Helvetica findfont 7.8 scalefont setfont
                {MARGIN_LEFT + 10} {cur_y} moveto ({self._esc(l)}) show
                grestore
                """
                self.add_raw(ps_t)
                cur_y -= 10.5
            cur_y -= 2

        _draw_block("1. THE HOOK (0-4s):", h_lines, lbl_color=(0.85, 0.20, 0.15))
        _draw_block("2. THE PAIN / GAP (4-15s):", p_lines, lbl_color=(0.85, 0.45, 0.05))
        _draw_block("3. THE SOLUTION & SCREEN DEMO (15-30s):", s_lines, lbl_color=(0.10, 0.55, 0.25))
        _draw_block("4. THE NO-BRAINER OFFER (30-40s):", o_lines, lbl_color=(0.106, 0.212, 0.365))
        _draw_block("5. FINAL CALL TO ACTION (40-45s):", c_lines, lbl_color=(0.55, 0.15, 0.65))

        self.current_y -= (card_h + 8)

    def draw_table_packages(self):
        rows = [
            ("1. WhatsApp Mobile Catalog", "PKR 10,000", "Small Boutiques, Unstitched Resellers, Tailors", "Fast Mobile Catalog, 1-Click WhatsApp Cart, Basic Google Maps, 0 Monthly Fees"),
            ("2. Full E-Commerce Store", "PKR 15,000", "Pret Brands, Stitched Wear, Shoes/Bags", "Shopify / Custom Web Store, Auto COD, Size Charts, Trax/TCS linking, Card Gateways"),
            ("3. Full Digitalization + AI Reels", "PKR 20,000", "Brands wanting complete transformation & sales", "Full Store + 5 Viral AI Model Video Reels + Google SEO + Bio Overhaul + Ad Creatives"),
            ("4. AI Fashion Content Retainer", "Custom Monthly", "Ongoing monthly social media scaling", "12 to 20 Monthly AI Model Reels, Trending audio hooks, Catalog video showcases"),
        ]
        self.ensure_space(140)
        self.current_y -= 6
        y = self.current_y

        # Header
        ps_hdr = f"""
        gsave
        0.106 0.212 0.365 setrgbcolor
        {MARGIN_LEFT} {y - 18} {CONTENT_WIDTH} 18 rectfill
        1.0 1.0 1.0 setrgbcolor
        /Helvetica-Bold findfont 7.5 scalefont setfont
        {MARGIN_LEFT + 6} {y - 12} moveto (PACKAGE) show
        {MARGIN_LEFT + 125} {y - 12} moveto (PRICE) show
        {MARGIN_LEFT + 180} {y - 12} moveto (IDEAL CLIENT) show
        {MARGIN_LEFT + 325} {y - 12} moveto (KEY DELIVERABLES) show
        grestore
        """
        self.add_raw(ps_hdr)
        cur_y = y - 18

        for i, (pkg, prc, clt, deliv) in enumerate(rows):
            deliv_lines = self._wrap_text(deliv, 7.2, 185)
            row_h = max(18, 6 + len(deliv_lines) * 9.5)
            bg = "0.96 0.97 0.99" if i % 2 == 0 else "1.0 1.0 1.0"
            ps_row = f"""
            gsave
            {bg} setrgbcolor
            {MARGIN_LEFT} {cur_y - row_h} {CONTENT_WIDTH} {row_h} rectfill
            0.85 0.88 0.92 setrgbcolor
            {MARGIN_LEFT} {cur_y - row_h} {CONTENT_WIDTH} {row_h} rectstroke
            
            0.106 0.212 0.365 setrgbcolor
            /Helvetica-Bold findfont 7.5 scalefont setfont
            {MARGIN_LEFT + 6} {cur_y - 12} moveto ({self._esc(pkg)}) show
            
            0.85 0.35 0.05 setrgbcolor
            /Helvetica-Bold findfont 7.5 scalefont setfont
            {MARGIN_LEFT + 125} {cur_y - 12} moveto ({self._esc(prc)}) show
            
            0.20 0.20 0.25 setrgbcolor
            /Helvetica findfont 7.2 scalefont setfont
            {MARGIN_LEFT + 180} {cur_y - 12} moveto ({self._esc(clt[:30])}) show
            grestore
            """
            self.add_raw(ps_row)

            # Draw wrapped deliverables
            deliv_y = cur_y - 11
            for dl in deliv_lines:
                ps_dl = f"""
                gsave
                0.20 0.25 0.30 setrgbcolor
                /Helvetica findfont 7.2 scalefont setfont
                {MARGIN_LEFT + 325} {deliv_y} moveto ({self._esc(dl)}) show
                grestore
                """
                self.add_raw(ps_dl)
                deliv_y -= 9.5

            cur_y -= row_h

        self.current_y = cur_y - 10

    def _esc(self, s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _wrap_text(self, text: str, font_size: float, max_width: float) -> list[str]:
        chars_per_line = max(10, int(max_width / (font_size * 0.49)))
        words = text.split()
        lines = []
        cur_line = []
        cur_len = 0
        for w in words:
            if cur_len + len(w) + 1 <= chars_per_line:
                cur_line.append(w)
                cur_len += len(w) + 1
            else:
                if cur_line:
                    lines.append(" ".join(cur_line))
                cur_line = [w]
                cur_len = len(w)
        if cur_line:
            lines.append(" ".join(cur_line))
        return lines

    def render_all(self) -> str:
        total_p = len(self.pages)
        out = [
            "%!PS-Adobe-3.0",
            f"%%Pages: {total_p}",
            f"%%BoundingBox: 0 0 {int(PAGE_WIDTH)} {int(PAGE_HEIGHT)}",
            "%%DocumentPaperSizes: A4",
            "%%EndComments",
        ]
        for p_idx, p_lines in enumerate(self.pages, start=1):
            out.append(f"%%Page: {p_idx} {p_idx}")
            out.append(self.draw_header_footer(p_idx, total_p))
            out.extend(p_lines)
            out.append("showpage\n")
        out.append("%%EOF")
        return "\n".join(out)


def build_master_reels_ps(w: ReelsPSWriter):
    # PAGE 1: COVER + REELS 1, 2
    w.draw_header_banner(
        title="MALIKAXIOM — MASTER VIDEO REELS & CONTENT PLAYBOOK",
        subtitle="14 Complete High-Converting Reels from Hook to Final CTA (General Digitalization & Clothing Niche)",
        badge="Packages: 10K WhatsApp Catalog | 15K E-Com Store | 20K Full Digitalization + AI Model Reels",
    )

    w.draw_section_heading("PART 1: GENERAL BUSINESS DIGITALIZATION & LOCAL STORES (REELS 1-5)")

    w.draw_reel_card(
        number=1,
        title="The 'Price in DM' Nightmare",
        target="Boutiques, DM Sellers, Footwear",
        duration="45s",
        angle="Frustration -> 1-Click WhatsApp Store Relief",
        hook="\"Agar aap abhi bhi customers ko Instagram DMs mein 'Price in DM' likh kar pictures bhej rahe hain... to aap daily 10 mein se 7 orders lose kar rahe hain!\"",
        pain="Customer 2 ghantay wait nahi karta! Jab tak aap reply karte hain, wo kisi aur page se order book kar chuka hota hai.",
        solution="MalikAxiom ultra-fast Mobile Online Store + 1-Click WhatsApp Checkout banata hai jahan customer direct size select karke WhatsApp par order slip bhejta hai.",
        offer="Complete professional setup starts from PKR 10,000 to 20,000 (Live in 24-48 hours, zero monthly fees).",
        cta="Abhi DM mein 'STORE' likhein ya WhatsApp karein (+92 313 0466400) for a 15-second live demo!"
    )

    w.draw_reel_card(
        number=2,
        title="The 10,000 PKR Digital Store Reality Check",
        target="Small Retailers, Local Shops, Tailors",
        duration="40s",
        angle="Agency Overpricing vs MalikAxiom Transparency",
        hook="\"Market mein digital agencies aapse ek aam website ka 50,000 se 80,000 maangti hain? Yeh dekhein asal reality!\"",
        pain="Local businesses ko 50k ke complex software ki nahi, balki ek aisi fast mobile website ki zaroorat hoti hai jisse direct customer calls aur WhatsApp orders aaein.",
        solution="Package includes: Fast Mobile Store, Google Maps SEO setup, 1-Click WhatsApp Orders, aur Social starter branding.",
        offer="Starting from just PKR 10,000 - 20,000 with zero hidden charges.",
        cta="Comment ya DM karein 'SETUP' aur apna free demo link haasil karein!"
    )

    # PAGE 2: REELS 3, 4, 5
    w.new_page()
    w.draw_reel_card(
        number=3,
        title="Google Maps Par Traffic Hai Lekin Sales Kahan Hain?",
        target="Retailers, Cafes, Salons with Google Maps",
        duration="42s",
        angle="Traffic Leak -> 1-Click Capture",
        hook="\"Aapki shop Google Maps par show hoti hai, 4.8 star rating bhi hai... lekin phone par direct orders kyun nahi aa rahe?\"",
        pain="Google par aane wala 80% customer pehle collection/menu dekhna chahta hai. Link na milne par wo competitor ke paas chala jata hai!",
        solution="Hum Google listing ke sath 1-click Digital Catalog & WhatsApp Order Button connect karte hain.",
        offer="Complete setup live karwayein starting from PKR 10,000.",
        cta="Comment karein 'MAPS' for a free Google Business Audit!"
    )

    w.draw_reel_card(
        number=4,
        title="Clinics & Doctors: Receptionist Ki Calls Ka Bojh Khatam",
        target="Dentists, Dermatologists, Aesthetic Clinics",
        duration="48s",
        angle="Zero Missed Patients & Automation",
        hook="\"Kya aapke clinic par patients ki appointment calls attend karte karte staff thak jata hai aur adhay patients miss ho jaate hain?\"",
        pain="Peak hours mein busy phone lines ki waja se patient doosre clinic chala jata hai aur no-shows barh jate hain.",
        solution="1-Click WhatsApp Patient Slot Booking & Automated WhatsApp Reminder System.",
        offer="Live within 48 hours for healthcare practices.",
        cta="DM karein 'CLINIC' for live healthcare booking demo!"
    )

    w.draw_reel_card(
        number=5,
        title="Case Study: 24 Ghantay Mein Offline Shop Se Online Machine",
        target="Skeptical Business Owners (Proof of Work)",
        duration="50s",
        angle="Real Transformation Story (Liberty Market LHR)",
        hook="\"Humne Liberty Market Lahore ke ek local boutique ka poora business sirf 24 ghantay mein digitalize kiya... Yeh raha result!\"",
        pain="Pehle sirf walk-in aur manual WhatsApp photos par chal rahe thay, daily 20-30 inquiries waste ho rahi theen.",
        solution="Fast mobile store, automated WhatsApp checkout, aur Google SEO. Ab customer direct catalog dekh kar order karta hai!",
        offer="Complete transformation package at PKR 10,000 - 20,000.",
        cta="DM karein 'GROW' aur apne brand ka sample demo link haasil karein!"
    )

    # PAGE 3: PART 2 CLOTHING NICHE (REELS 6, 7, 8)
    w.new_page()
    w.draw_section_heading("PART 2: CLOTHING, BOUTIQUES & FASHION NICHE MASTER REELS (REELS 6-14)")

    w.draw_reel_card(
        number=6,
        title="10K vs 15K vs 20K Clothing Package Breakdown",
        target="Boutiques, Pret, Unstitched Brands",
        duration="45s",
        angle="Complete Package & Budget Transparency",
        hook="\"Agar aapka clothing brand ya boutique hai, to MalikAxiom se aapko 10K, 15K aur 20K mein kya kya milta hai? Yeh dekhein clear breakdown!\"",
        pain="10K = Fast WhatsApp Mobile Catalog. 15K = Full Shopify/Web Store + Auto COD + Courier linking.",
        solution="20K = Full Online Store + Google Maps + 5 Viral AI Fashion Model Video Reels!",
        offer="Transparent packages tailored for Pakistani fashion businesses.",
        cta="DM mein likhein 'CLOTHING' for sample portfolio!"
    )

    w.draw_reel_card(
        number=7,
        title="Khaadi / Limelight vs Aapka Local Boutique",
        target="Boutiques manually dealing in DMs",
        duration="42s",
        angle="Competitor Gap & Instant Checkout",
        hook="\"Khaadi aur Limelight daily hazaron dresses kaise bech lete hain jabke aap 10 customers ko DMs mein reply karte karte thak jate hain?\"",
        pain="Unke paas Automated Mobile Checkout System hai jahan customer 5 second mein order confirm kar deta hai.",
        solution="MalikAxiom same fast automated checkout ready karta hai for your boutique.",
        offer="Complete professional store setup at just PKR 15,000.",
        cta="DM karein 'AUTOMATE' to experience the live boutique store!"
    )

    w.draw_reel_card(
        number=8,
        title="AI Fashion Reels — 50,000 Ka Model Shoot Kharcha Khatam!",
        target="Clothing Brands needing High-End Content",
        duration="45s",
        angle="Cost Savings on Model Shoots via AI Generation",
        hook="\"Kya aap bhi har naye dress ke shoot ke liye model aur studio ko 40 se 50 hazaar de de kar thak chuke hain?\"",
        pain="Expensive shoots har collection par afford karna mushkil hota hai.",
        solution="MalikAxiom aapke suits ko High-Quality Walking AI Model Reels mein convert karta hai with trending audio hooks!",
        offer="Included in our 20K Full Transformation Package (5 Viral AI Reels).",
        cta="DM mein likhein 'AI REELS' for sample AI dress shoot!"
    )

    # PAGE 4: CLOTHING REELS 9, 10, 11
    w.new_page()
    w.draw_reel_card(
        number=9,
        title="Shopify vs 10K WhatsApp Catalog — Aapke Liye Kya Behtar Hai?",
        target="Small vs Established Clothing Brands",
        duration="40s",
        angle="Expert Guidance & Zero Wasted Money",
        hook="\"Agar aapka clothing brand naya hai, to Shopify par har maheene 10 hazaar subscription zaya mat karein! Yeh suniye...\"",
        pain="20-50 designs wale brand ko heavy Shopify bill ki zaroorat nahi.",
        solution="10K WhatsApp Catalog = Best for small brands (Zero monthly bill). 15K-20K Shopify/Custom Store = Best for 500+ SKUs.",
        offer="Honest architecture matching for your growth stage.",
        cta="DM karein 'CONSULT' for honest advice on your store!"
    )

    w.draw_reel_card(
        number=10,
        title="Sham Ki 20 Khati hui Slips vs 1-Click Automated Invoice",
        target="Boutique Owners spending hours dispatching",
        duration="42s",
        angle="Logistics Relief & Zero Parcel Returns",
        hook="\"Har sham orders dispatch karte waqt 20-30 kaghaz ki slips hath se likhte likhte hath thak jata hai?\"",
        pain="Wrong address on paper slip = parcel return loss & rider delivery wasted.",
        solution="1-Click Automated Customer Invoice & Courier Slip Generator directly from website.",
        offer="Setup starts from PKR 10,000 with zero monthly fees.",
        cta="DM karein 'DISPATCH' to automate your order packing!"
    )

    w.draw_reel_card(
        number=11,
        title="Suit Ki Photo Achi Hai Lekin Sale Zero Kyun?",
        target="Fashion sellers with great photos but low sales",
        duration="44s",
        angle="Conversion Rate Optimization (CRO) for Dresses",
        hook="\"Aapke suits ki quality bhi A-one hai, pictures bhi DSLR se li hain... lekin phir bhi orders kyun nahi aa rahe?\"",
        pain="Customer ko 3 cheezein foran chahiye: Exact Price, Detailed Size Chart, aur Instant COD button. DMs mein yeh maangte maangte mood khatam ho jata hai!",
        solution="High-converting product pages with fabric details, size chart, and instant WhatsApp COD order.",
        offer="Complete mobile store redesign starting from PKR 10,000 to 15,000.",
        cta="DM karein 'CONVERT' for free design layout audit!"
    )

    # PAGE 5: CLOTHING REELS 12, 13, 14 & SUMMARY TABLE
    w.new_page()
    w.draw_reel_card(
        number=12,
        title="Azam Market / Ichhra B2B Wholesalers & Fabric Traders",
        target="Fabric Wholesalers & Kapra Manufacturers",
        duration="45s",
        angle="B2B Bulk Volume Ordering",
        hook="\"Azam Market, Ichhra ya Faisalabad ke fabric wholesalers jo puray Pakistan mein kapra supply karte hain... yeh video aapke liye hai!\"",
        pain="Har retailer ko rozana WhatsApp par 100-100 pictures bhejna aur stock check karna band karein!",
        solution="B2B Bulk Digital Catalog jahan se nationwide retailers volume/than select karke bulk order book karte hain.",
        offer="Setup starting at PKR 15,000 for fabric traders.",
        cta="DM karein 'WHOLESALE' for B2B catalog demo!"
    )

    w.draw_reel_card(
        number=13,
        title="Dead Instagram Page to Active Clothing Brand in 7 Days",
        target="Dormant clothing pages needing a revival",
        duration="50s",
        angle="360° Complete 7-Day Revival Plan",
        hook="\"Agar aapka clothing page ban kar khara hai aur koi sale nahi aa rahi, to yeh 7-Day Transformation Plan dekhein!\"",
        pain="Day 1-3: Fast Mobile Store + COD. Day 4-7: 5 Viral AI Model Reels with trending hooks for organic reach!",
        solution="Complete 360-degree brand transformation.",
        offer="Full Package at PKR 20,000 with everything included.",
        cta="DM karein 'REVAMP' to start your 7-day brand launch!"
    )

    w.draw_reel_card(
        number=14,
        title="Cash On Delivery (COD) & Courier Integration Setup",
        target="Clothing brands dispatching via TCS/Trax/Leopards",
        duration="40s",
        angle="Automated Logistics & Tracking",
        hook="\"Boutique owners: Kya aap abhi bhi Trax, TCS ya Leopards ke portal par ek ek customer ka address manually copy-paste karte hain?\"",
        pain="Copy-paste errors lead to wrong dispatches and customer delivery complaints.",
        solution="Direct Courier API integration: 1-click consignment booking + automated customer WhatsApp tracking links!",
        offer="Included in our PKR 15,000 E-Commerce Store setup.",
        cta="DM karein 'COURIER' to automate your courier portal!"
    )

    w.draw_section_heading("MALIKAXIOM CLOTHING PACKAGES SUMMARY TABLE")
    w.draw_table_packages()


def main():
    w = ReelsPSWriter()
    build_master_reels_ps(w)
    ps_output = w.render_all()

    project_root = Path(__file__).resolve().parent.parent
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True, parents=True)

    ps_path = output_dir / "MalikAxiom_Master_Reels_Playbook.ps"
    pdf_path = output_dir / "MalikAxiom_Master_Reels_Playbook.pdf"

    ps_path.write_text(ps_output, encoding="utf-8")
    print(f"PostScript written: {ps_path}")

    cmd = ["ps2pdf", str(ps_path), str(pdf_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and pdf_path.exists():
        print(f"✅ Master Reels Playbook PDF created: {pdf_path} ({pdf_path.stat().st_size} bytes)")
        if ps_path.exists():
            ps_path.unlink()
    else:
        print(f"Error compiling PDF: {res.stderr}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
