#!/usr/bin/env python3
"""Generates a professional, print-ready PDF manual for MalikAxiom Cold Calling SOP.

Uses standard PostScript rendering and compiles via ps2pdf into output/MalikAxiom_Cold_Calling_SOP_Manual.pdf.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PAGE_WIDTH = 595.28   # A4 width
PAGE_HEIGHT = 841.89  # A4 height
MARGIN_LEFT = 45
MARGIN_RIGHT = 550
CONTENT_WIDTH = MARGIN_RIGHT - MARGIN_LEFT
TOP_Y = 785
BOTTOM_Y = 55


class PSWriter:
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
        # Top banner line (pages after page 1)
        if page_idx > 1:
            lines.append(f"""
            gsave
            0.85 0.88 0.92 setrgbcolor
            {MARGIN_LEFT} 810 moveto {MARGIN_RIGHT} 810 lineto stroke
            /Helvetica-Bold findfont 8 scalefont setfont
            0.11 0.21 0.36 setrgbcolor
            {MARGIN_LEFT} 815 moveto (MALIKAXIOM TECHNOLOGY  |  COLD CALLING SALES PLAYBOOK & SOP) show
            /Helvetica findfont 8 scalefont setfont
            0.45 0.50 0.55 setrgbcolor
            430 815 moveto (CONFIDENTIAL - INTERNAL TRAINING) show
            grestore
            """)

        # Bottom footer line on all pages
        lines.append(f"""
        gsave
        0.85 0.88 0.92 setrgbcolor
        {MARGIN_LEFT} 40 moveto {MARGIN_RIGHT} 40 lineto stroke
        /Helvetica findfont 8 scalefont setfont
        0.45 0.50 0.55 setrgbcolor
        {MARGIN_LEFT} 28 moveto (MalikAxiom Technology - https://malikaxiomtech.com - WhatsApp: +92 313 0466400) show
        /Helvetica-Bold findfont 8 scalefont setfont
        0.11 0.21 0.36 setrgbcolor
        500 28 moveto (Page {page_idx} of {total_pages}) show
        grestore
        """)
        return "\n".join(lines)

    def draw_cover_header(self, title: str, subtitle: str, meta: str):
        self.ensure_space(140)
        y = self.current_y
        ps = f"""
        gsave
        % Header gradient-like solid bar
        0.106 0.212 0.365 setrgbcolor
        {MARGIN_LEFT} {y - 85} {CONTENT_WIDTH} 95 rectfill
        
        % Gold accent line
        0.90 0.45 0.10 setrgbcolor
        {MARGIN_LEFT} {y - 88} {CONTENT_WIDTH} 3 rectfill
        
        % Title text
        1.0 1.0 1.0 setrgbcolor
        /Helvetica-Bold findfont 16 scalefont setfont
        {MARGIN_LEFT + 15} {y - 25} moveto ({self._esc(title)}) show
        
        /Helvetica-Bold findfont 11 scalefont setfont
        0.92 0.75 0.40 setrgbcolor
        {MARGIN_LEFT + 15} {y - 45} moveto ({self._esc(subtitle)}) show
        
        /Helvetica findfont 8.5 scalefont setfont
        0.85 0.90 0.95 setrgbcolor
        {MARGIN_LEFT + 15} {y - 68} moveto ({self._esc(meta)}) show
        grestore
        """
        self.add_raw(ps)
        self.current_y -= 105

    def draw_section_heading(self, text: str):
        self.ensure_space(45)
        self.current_y -= 10
        y = self.current_y
        ps = f"""
        gsave
        % Left accent bar
        0.106 0.212 0.365 setrgbcolor
        {MARGIN_LEFT} {y - 18} 4 18 rectfill
        
        % Heading text
        0.106 0.212 0.365 setrgbcolor
        /Helvetica-Bold findfont 12 scalefont setfont
        {MARGIN_LEFT + 10} {y - 14} moveto ({self._esc(text)}) show
        
        % Underline
        0.85 0.88 0.92 setrgbcolor
        {MARGIN_LEFT + 10} {y - 20} moveto {MARGIN_RIGHT} {y - 20} lineto stroke
        grestore
        """
        self.add_raw(ps)
        self.current_y -= 28

    def draw_subheading(self, text: str):
        self.ensure_space(30)
        self.current_y -= 5
        y = self.current_y
        ps = f"""
        gsave
        0.85 0.35 0.05 setrgbcolor
        /Helvetica-Bold findfont 10 scalefont setfont
        {MARGIN_LEFT} {y - 10} moveto ({self._esc(text)}) show
        grestore
        """
        self.add_raw(ps)
        self.current_y -= 18

    def draw_paragraph(self, text: str, font_size: float = 9.0, is_bold: bool = False, color_rgb=(0.2, 0.2, 0.25)):
        font = "Helvetica-Bold" if is_bold else "Helvetica"
        lines = self._wrap_text(text, font_size, CONTENT_WIDTH)
        for line in lines:
            self.ensure_space(font_size + 5)
            y = self.current_y
            r, g, b = color_rgb
            ps = f"""
            gsave
            {r} {g} {b} setrgbcolor
            /{font} findfont {font_size} scalefont setfont
            {MARGIN_LEFT} {y - font_size} moveto ({self._esc(line)}) show
            grestore
            """
            self.add_raw(ps)
            self.current_y -= (font_size + 4)

    def draw_bullet(self, text: str, font_size: float = 8.5, bullet_char: str = "•", color_rgb=(0.2, 0.2, 0.25)):
        indent = 16
        lines = self._wrap_text(text, font_size, CONTENT_WIDTH - indent)
        for i, line in enumerate(lines):
            self.ensure_space(font_size + 5)
            y = self.current_y
            r, g, b = color_rgb
            b_sym = f"({bullet_char}) show" if i == 0 else ""
            ps = f"""
            gsave
            /{'Helvetica-Bold' if i == 0 else 'Helvetica'} findfont {font_size} scalefont setfont
            0.106 0.212 0.365 setrgbcolor
            {MARGIN_LEFT + 2} {y - font_size} moveto {b_sym}
            {r} {g} {b} setrgbcolor
            /Helvetica findfont {font_size} scalefont setfont
            {MARGIN_LEFT + indent} {y - font_size} moveto ({self._esc(line)}) show
            grestore
            """
            self.add_raw(ps)
            self.current_y -= (font_size + 4)

    def draw_callout_box(self, speaker: str, script_text: str, tag: str = "SCRIPT", tag_color=(0.106, 0.212, 0.365)):
        # Measure wrapped lines
        lines = self._wrap_text(script_text, 8.5, CONTENT_WIDTH - 25)
        box_height = 28 + len(lines) * 12.5
        self.ensure_space(box_height + 15)
        self.current_y -= 6
        y = self.current_y
        tr, tg, tb = tag_color

        ps = f"""
        gsave
        % Light background
        0.96 0.97 0.985 setrgbcolor
        {MARGIN_LEFT} {y - box_height} {CONTENT_WIDTH} {box_height} rectfill
        
        % Border
        0.82 0.85 0.90 setrgbcolor
        {MARGIN_LEFT} {y - box_height} {CONTENT_WIDTH} {box_height} rectstroke
        
        % Left thick colored accent
        {tr} {tg} {tb} setrgbcolor
        {MARGIN_LEFT} {y - box_height} 4 {box_height} rectfill
        
        % Speaker Title Tag
        /Helvetica-Bold findfont 8.5 scalefont setfont
        {tr} {tg} {tb} setrgbcolor
        {MARGIN_LEFT + 12} {y - 14} moveto ({self._esc(f"[{tag}]  {speaker}")}) show
        grestore
        """
        self.add_raw(ps)
        
        text_y = y - 28
        for line in lines:
            ps_line = f"""
            gsave
            0.15 0.15 0.20 setrgbcolor
            /Helvetica-Oblique findfont 8.5 scalefont setfont
            {MARGIN_LEFT + 12} {text_y} moveto ({self._esc(line)}) show
            grestore
            """
            self.add_raw(ps_line)
            text_y -= 12.5

        self.current_y -= (box_height + 8)

    def draw_objection_card(self, objection: str, customer_mindset: str, rebuttal: str):
        reb_lines = self._wrap_text(rebuttal, 8.2, CONTENT_WIDTH - 25)
        mind_lines = self._wrap_text(f"Psychology: {customer_mindset}", 7.8, CONTENT_WIDTH - 25)
        card_h = 32 + len(mind_lines) * 10 + len(reb_lines) * 11.5
        self.ensure_space(card_h + 10)
        self.current_y -= 4
        y = self.current_y

        ps = f"""
        gsave
        % Card background
        0.97 0.97 0.98 setrgbcolor
        {MARGIN_LEFT} {y - card_h} {CONTENT_WIDTH} {card_h} rectfill
        0.84 0.86 0.90 setrgbcolor
        {MARGIN_LEFT} {y - card_h} {CONTENT_WIDTH} {card_h} rectstroke
        
        % Red / Warning Accent on left
        0.85 0.22 0.15 setrgbcolor
        {MARGIN_LEFT} {y - card_h} 4 {card_h} rectfill
        
        % Objection Title
        0.85 0.22 0.15 setrgbcolor
        /Helvetica-Bold findfont 9.0 scalefont setfont
        {MARGIN_LEFT + 12} {y - 13} moveto ({self._esc("🔴 OBJECTION: " + objection)}) show
        grestore
        """
        self.add_raw(ps)

        cur_y = y - 24
        for mline in mind_lines:
            ps_m = f"""
            gsave
            0.45 0.50 0.55 setrgbcolor
            /Helvetica-Oblique findfont 7.8 scalefont setfont
            {MARGIN_LEFT + 12} {cur_y} moveto ({self._esc(mline)}) show
            grestore
            """
            self.add_raw(ps_m)
            cur_y -= 10

        cur_y -= 2
        ps_tag = f"""
        gsave
        0.10 0.50 0.25 setrgbcolor
        /Helvetica-Bold findfont 8.0 scalefont setfont
        {MARGIN_LEFT + 12} {cur_y} moveto ({self._esc("✅ WORD-FOR-WORD RESPONSE:")}) show
        grestore
        """
        self.add_raw(ps_tag)
        cur_y -= 11

        for rline in reb_lines:
            ps_r = f"""
            gsave
            0.12 0.15 0.20 setrgbcolor
            /Helvetica findfont 8.2 scalefont setfont
            {MARGIN_LEFT + 12} {cur_y} moveto ({self._esc(rline)}) show
            grestore
            """
            self.add_raw(ps_r)
            cur_y -= 11.5

        self.current_y -= (card_h + 8)

    def _esc(self, s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _wrap_text(self, text: str, font_size: float, max_width: float) -> list[str]:
        # Approximate char width ~ 0.52 * font_size for Helvetica
        chars_per_line = max(10, int(max_width / (font_size * 0.50)))
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


def build_playbook_ps(writer: PSWriter):
    # PAGE 1: COVER & OVERVIEW
    writer.draw_cover_header(
        title="MALIKAXIOM TECHNOLOGY — COLD CALLING SALES PLAYBOOK",
        subtitle="Standard Operating Procedure (SOP) & Master Scripts Manual for Sales Agents",
        meta="Flagship Offer: PKR 10,000 – 20,000 Business Digitalization | Target: Pakistani Local Businesses",
    )

    writer.draw_section_heading("1. CORE VALUE PROPOSITION & COMPANY PROFILE")
    writer.draw_paragraph(
        "MalikAxiom Technology empowers local Pakistani SMEs, clinics, boutiques, retailers, and restaurants "
        "to solve operational challenges and generate predictable sales through modern web development, "
        "mobile online stores, and AI business automation."
    )
    writer.draw_bullet("Flagship Service: Complete Business Digitalization & Mobile Store (Starting PKR 10,000 - 20,000).")
    writer.draw_bullet("Core Deliverables: Fast Mobile Website, 1-Click WhatsApp Ordering Button, Google Maps SEO, Starter Social Setup.")
    writer.draw_bullet("Trust Badges: 7+ years development experience, 20+ international projects delivered, zero hidden fees.")
    writer.draw_bullet("Official Channels: Web: https://malikaxiomtech.com | WhatsApp: +92 313 0466400 | Haider Nawaz.")

    writer.draw_section_heading("2. CALLER'S MINDSET & THE FIRST 10 SECONDS")
    writer.draw_paragraph(
        "Golden Rule #1: The goal of a cold call is NEVER to close the deal on phone. The sole objective is to earn "
        "permission to send a 15-second personalized WhatsApp demo video link.",
        is_bold=True
    )
    writer.draw_bullet("Pre-Call Reconnaissance: Check M7 Dashboard for Business Name, City, Google Rating, and Website status.")
    writer.draw_bullet("Positive Terminology Rule: Never say 'Aapke business mein problem hai'. Always say 'Digital Growth Opportunity' or 'Next-Level Automation'.")
    writer.draw_bullet("Tone & Energy: Friendly, conversational Roman Urdu/English mix. Maintain confident, enthusiastic pacing.")

    writer.draw_section_heading("3. THE 5-STEP COLD CALL ANATOMY")
    writer.draw_bullet("Step 1 (0-5s) - The Warm Hook: Assalam-o-Alaikum + Decision Maker confirmation.")
    writer.draw_bullet("Step 2 (5-15s) - The Specific Compliment: Reference their Google rating, catalog, or physical outlet.")
    writer.draw_bullet("Step 3 (15-30s) - The Gap & Solution: Highlight missing 1-click WhatsApp order flow or mobile store.")
    writer.draw_bullet("Step 4 (30-40s) - The No-Brainer Offer: Mention clear starter pricing (PKR 10,000 - 20,000).")
    writer.draw_bullet("Step 5 (40-50s) - The Frictionless CTA: Ask permission to drop the 15-second WhatsApp demo video.")

    # PAGE 2: SITUATION SCRIPTS (GATEKEEPER, NO WEBSITE, INSTAGRAM SELLER)
    writer.new_page()
    writer.draw_section_heading("4. SITUATION-SPECIFIC MASTER SCRIPTS")

    writer.draw_subheading("Scenario A: Bypassing the Gatekeeper / Counter Staff")
    writer.draw_callout_box(
        speaker="Agent to Staff / Receptionist",
        script_text="Assalam-o-Alaikum! Main Haider baat kar raha hoon MalikAxiom Technology se. "
                    "Mujhe [Business Name] ke owner ya marketing head se 30 seconds ke liye baat karni thi unke online orders aur business setup ke hawale se. Kya wo is waqt available hain?",
        tag="GATEKEEPER HOOK"
    )
    writer.draw_callout_box(
        speaker="If Staff asks 'Kis silsile mein baat karni hai?'",
        script_text="Actually unki Google Maps listing aur online profile dekhi thi, uske hawale se ek quick growth update share karni thi. Unka direct WhatsApp number mil sakta hai ya call transfer ho sakti hai?",
        tag="STAFF REBUTTAL",
        tag_color=(0.85, 0.35, 0.05)
    )

    writer.draw_subheading("Scenario B: Local Store / Offline Business (No Website, Only Google Maps)")
    writer.draw_callout_box(
        speaker="Agent to Owner (Boutique, Salon, Retail, Restaurant)",
        script_text="Assalam-o-Alaikum [Owner Name/Sir]! Main Haider baat kar raha hoon MalikAxiom Technology se. "
                    "Aapka [Business Name] Google Maps par dekha—mashallah collection aur reviews aapke kafi zabardast hain! "
                    "Sir quick baat yeh karni thi ke aapka Google par traffic to aa raha hai, lekin abhi koi direct mobile website ya 1-click WhatsApp order button nahi laga hua. "
                    "Hum local businesses ko complete digital setup provide karte hain—jis mein fast mobile website, Google SEO aur 1-click WhatsApp orders shamil hain—aur yeh complete setup sirf PKR 10,000 se 20,000 se start hota hai. "
                    "Kya main aapko WhatsApp par ek 15-second ka sample demo link share kar doon taake aap dekh sakein ke yeh aapke business mein orders kaise barhayega?",
        tag="NO-WEBSITE SCRIPT"
    )

    writer.draw_subheading("Scenario C: Instagram / WhatsApp DM Sellers (Manual Order Slips)")
    writer.draw_callout_box(
        speaker="Agent to Online Brand / Instagram Seller",
        script_text="Assalam-o-Alaikum [Name]! Haider baat kar raha hoon MalikAxiom se. "
                    "Aapka Instagram page dekha—designs aapke bohot attractive hain! Lekin ek cheez note ki ke customers ko order confirm karne ke liye DMs mein ghanton wait karna parta hai ya manually slips bhejni parti hain. "
                    "Humne similar brands ke liye Automated 24/7 Mobile Online Store + COD Integration setup kiya hai jahan customer direct order place karta hai aur aapka 80% manual time bach jata hai. "
                    "Aap isi number par WhatsApp use kar rahe hain? Main aapko 1 chota sa demo video link bhejta hoon ke yeh live kaise work karta hai.",
        tag="E-COMMERCE SCRIPT"
    )

    # PAGE 3: CLINICS, REVAMPS, FOLLOW-UPS & OBJECTION HANDLING
    writer.new_page()
    writer.draw_subheading("Scenario D: Clinics / Doctors / Healthcare (Patient Booking System)")
    writer.draw_callout_box(
        speaker="Agent to Doctor / Clinic Manager",
        script_text="Assalam-o-Alaikum Dr. Sahab! Haider Nawaz from MalikAxiom Technology. "
                    "Aapke clinic ki profile dekhi Google par—patient reviews kafi positive hain. "
                    "Sir hum clinics ke liye Online Patient Booking aur Automated WhatsApp Reminder System setup karte hain taake patient direct mobile se slot book kare aur staff ko bar bar phone attend na karna pare. "
                    "Kya main aapko WhatsApp par ek quick clinic demo overview bhej doon jab aap free hon to dekh sakein?",
        tag="CLINIC SCRIPT"
    )

    writer.draw_subheading("Scenario E: Follow-Up Call (After Sending WhatsApp Demo)")
    writer.draw_callout_box(
        speaker="Agent to Prospective Client (Next Day)",
        script_text="Assalam-o-Alaikum [Client Name]! Haider baat kar raha hoon MalikAxiom se. "
                    "Sir kal maine aapko WhatsApp par [Business Name] ke liye online demo aur website sample bheja tha. "
                    "Sir kya aapne wo 15-second sample dekha? Kaisa laga aapko design? Hum is mein aapka logo aur complete catalog attach karke kal tak live kar sakte hain.",
        tag="FOLLOW-UP SCRIPT"
    )

    writer.draw_section_heading("5. THE MASTER OBJECTION HANDLING VAULT")

    writer.draw_objection_card(
        objection="Mujhe zaroorat nahi hai / Hamara offline kaam theek chal raha hai",
        customer_mindset="Complacent, doesn't want change or unexpected risk.",
        rebuttal="Bilkul sahi keh rahe hain Sir! Offline walk-in to aapka established hai mashallah. Lekin aaj kal 70% log pehle mobile par search karte hain. Agar 1 clean mobile catalog ho to wahi customers jo ghar baithe hain direct aapko WhatsApp par orders dete hain. Main koi advance commitment nahi maang raha, sirf 1 sample link dekhein—pasand aaye to agay baat karein gay."
    )

    writer.draw_objection_card(
        objection="Details WhatsApp par bhej dein (The Polite Brush-Off)",
        customer_mindset="Wants to end the call quickly without confronting you.",
        rebuttal="Bilkul Sir, main abhi isi number par aapko portfolio aur 15-second ka demo link bhej raha hoon. Aapka good name [Name] hi hai na? Main abhi message drop karta hoon, aap 2 minute nikaal kar dekh lijiyega, phir sham mein 5 baje ek quick feedback ke liye touch base karoon ga."
    )

    # PAGE 4: MORE OBJECTIONS, WHATSAPP TEMPLATES & CALLER CHECKLIST
    writer.new_page()
    writer.draw_objection_card(
        objection="Bohat mehanga hoga / Hamara budget nahi hai",
        customer_mindset="Fears high agency quotes of 50k-100k PKR.",
        rebuttal="Sir isi liye to humne specially local Pakistani businesses ke liye customized packages banaye hain. Market mein agencies 50-60 hazaar charge karti hain, jabke hamara complete professional setup sirf PKR 10,000 se 20,000 mein complete ready ho jata hai with zero monthly extra charges. Is budget mein aapko full store + WhatsApp integration mil rahi hai."
    )

    writer.draw_objection_card(
        objection="Pehle se hamara developer / agency kaam kar rahi hai",
        customer_mindset="Loyal or locked into current vendor.",
        rebuttal="Bohat achi baat hai Sir! Hum aapke current developer ko replace nahi kar rahe. Sirf ek bar hamara AI Automation & 1-Click WhatsApp Ordering tool dekh lein, agar aapko lage ke yeh aapki sales barha sakta hai to aap apne developer se bhi integrate karwa sakte hain ya humse help le sakte hain."
    )

    writer.draw_section_heading("6. POST-CALL WHATSAPP MESSAGE TEMPLATE")
    writer.draw_paragraph("Send this message within 60 seconds of ending the call:", is_bold=True)
    writer.draw_callout_box(
        speaker="Immediate WhatsApp Follow-Up Message",
        script_text="Assalam o Alaikum [Client Name / Owner] 👋\n"
                    "Call par baat karke bohot acha laga! Jaisa ke discuss hua, yeh raha aapke business [Business Name] ke liye hamara quick digital setup demo link:\n"
                    "🌐 Live Demo: https://malikaxiomtech.com/demo\n"
                    "🛍️ Features: Mobile Store + 1-Click WhatsApp Ordering + COD Setup\n"
                    "💰 Complete Setup: Starting from PKR 10,000 – 20,000 (One-time)\n"
                    "Aap isko 30 seconds mein review kar lein, phir hum sham mein connect karte hain.\n"
                    "— Haider Nawaz | MalikAxiom Technology | 📱 WhatsApp: 0313 0466400",
        tag="WHATSAPP TEMPLATE",
        tag_color=(0.10, 0.55, 0.30)
    )

    writer.draw_section_heading("7. DAILY CALLER DOS & DON'TS CHECKLIST")
    writer.draw_bullet("DO: Confirm business name and city from M7 dashboard before dialing.", color_rgb=(0.10, 0.50, 0.20))
    writer.draw_bullet("DO: Smile while speaking—warmth and confidence carry through the phone voice.", color_rgb=(0.10, 0.50, 0.20))
    writer.draw_bullet("DO: Always deliver the core pitch within 45 seconds and ask for WhatsApp permission.", color_rgb=(0.10, 0.50, 0.20))
    writer.draw_bullet("DO: Record call notes on M7 Dashboard immediately (CONTACT FIRST / CONTACT LATER).", color_rgb=(0.10, 0.50, 0.20))
    writer.draw_bullet("DON'T: Never argue with a lead or use negative words like 'nuqs' or 'problems'.", color_rgb=(0.80, 0.20, 0.15))
    writer.draw_bullet("DON'T: Never give a lengthy technical lecture on coding/hosting during cold call.", color_rgb=(0.80, 0.20, 0.15))
    writer.draw_bullet("DON'T: Never hang up without locking a specific follow-up time (e.g. 'Kal 3 baje').", color_rgb=(0.80, 0.20, 0.15))


def main():
    writer = PSWriter()
    build_playbook_ps(writer)
    ps_output = writer.render_all()

    project_root = Path(__file__).resolve().parent.parent
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True, parents=True)

    ps_path = output_dir / "MalikAxiom_Cold_Calling_SOP_Manual.ps"
    pdf_path = output_dir / "MalikAxiom_Cold_Calling_SOP_Manual.pdf"

    ps_path.write_text(ps_output, encoding="utf-8")
    print(f"PostScript generated: {ps_path} ({len(ps_output)} bytes)")

    cmd = ["ps2pdf", str(ps_path), str(pdf_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and pdf_path.exists():
        print(f"✅ PDF successfully compiled: {pdf_path} ({pdf_path.stat().st_size} bytes)")
        if ps_path.exists():
            ps_path.unlink()
    else:
        print(f"Error compiling PDF via ps2pdf: {res.stderr}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
