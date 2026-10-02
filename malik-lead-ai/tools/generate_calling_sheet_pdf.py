#!/usr/bin/env python3
"""Generates the clean, official MalikAxiom Final Cold Calling Sheet PDF.

Output: output/MalikAxiom_Final_Calling_Sheet.pdf
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PAGE_WIDTH = 595.28   # A4 width
PAGE_HEIGHT = 841.89  # A4 height
MARGIN_LEFT = 40
MARGIN_RIGHT = 555
CONTENT_WIDTH = MARGIN_RIGHT - MARGIN_LEFT
TOP_Y = 790
BOTTOM_Y = 50


class CallingSheetPSWriter:
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
            {MARGIN_LEFT} 817 moveto (MALIKAXIOM TECHNOLOGY  |  FINAL COLD CALLING DESK SCRIPT) show
            /Helvetica findfont 8 scalefont setfont
            0.45 0.50 0.55 setrgbcolor
            440 817 moveto (DAILY SALES CHEAT SHEET) show
            grestore
            """)

        lines.append(f"""
        gsave
        0.85 0.88 0.92 setrgbcolor
        {MARGIN_LEFT} 38 moveto {MARGIN_RIGHT} 38 lineto stroke
        /Helvetica findfont 8 scalefont setfont
        0.45 0.50 0.55 setrgbcolor
        {MARGIN_LEFT} 26 moveto (MalikAxiom Technology - Sales SOP - WhatsApp: +92 313 0466400) show
        /Helvetica-Bold findfont 8 scalefont setfont
        0.106 0.212 0.365 setrgbcolor
        505 26 moveto (Page {page_idx} of {total_pages}) show
        grestore
        """)
        return "\n".join(lines)

    def draw_header_banner(self, title: str, subtitle: str, badge: str):
        self.ensure_space(110)
        y = self.current_y
        ps = f"""
        gsave
        0.106 0.212 0.365 setrgbcolor
        {MARGIN_LEFT} {y - 68} {CONTENT_WIDTH} 74 rectfill
        
        0.90 0.45 0.10 setrgbcolor
        {MARGIN_LEFT} {y - 71} {CONTENT_WIDTH} 3 rectfill
        
        1.0 1.0 1.0 setrgbcolor
        /Helvetica-Bold findfont 14.5 scalefont setfont
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

    def draw_section_heading(self, text: str):
        self.ensure_space(36)
        self.current_y -= 6
        y = self.current_y
        ps = f"""
        gsave
        0.106 0.212 0.365 setrgbcolor
        {MARGIN_LEFT} {y - 15} 3.5 15 rectfill
        
        /Helvetica-Bold findfont 10.5 scalefont setfont
        0.106 0.212 0.365 setrgbcolor
        {MARGIN_LEFT + 9} {y - 12} moveto ({self._esc(text)}) show
        
        0.85 0.88 0.92 setrgbcolor
        {MARGIN_LEFT + 9} {y - 17} moveto {MARGIN_RIGHT} {y - 17} lineto stroke
        grestore
        """
        self.add_raw(ps)
        self.current_y -= 23

    def draw_dialogue(self, speaker: str, text: str, subtext: str = "", tag_color=(0.106, 0.212, 0.365)):
        lines = self._wrap_text(text, 8.3, CONTENT_WIDTH - 24)
        sub_lines = self._wrap_text(subtext, 7.6, CONTENT_WIDTH - 24) if subtext else []
        
        box_h = 20 + len(lines) * 11.5 + (len(sub_lines) * 10 + 6 if sub_lines else 0)
        self.ensure_space(box_h + 10)
        self.current_y -= 3
        y = self.current_y
        r, g, b = tag_color

        ps = f"""
        gsave
        0.965 0.975 0.985 setrgbcolor
        {MARGIN_LEFT} {y - box_h} {CONTENT_WIDTH} {box_h} rectfill
        
        0.83 0.86 0.90 setrgbcolor
        {MARGIN_LEFT} {y - box_h} {CONTENT_WIDTH} {box_h} rectstroke
        
        {r} {g} {b} setrgbcolor
        {MARGIN_LEFT} {y - box_h} 3.5 {box_h} rectfill
        
        /Helvetica-Bold findfont 8.0 scalefont setfont
        {r} {g} {b} setrgbcolor
        {MARGIN_LEFT + 10} {y - 12} moveto ({self._esc(speaker)}) show
        grestore
        """
        self.add_raw(ps)

        cur_y = y - 24
        for l in lines:
            ps_l = f"""
            gsave
            0.12 0.15 0.20 setrgbcolor
            /Helvetica-Oblique findfont 8.3 scalefont setfont
            {MARGIN_LEFT + 10} {cur_y} moveto ({self._esc(l)}) show
            grestore
            """
            self.add_raw(ps_l)
            cur_y -= 11.5

        if sub_lines:
            cur_y -= 2
            for sl in sub_lines:
                ps_sl = f"""
                gsave
                0.40 0.45 0.50 setrgbcolor
                /Helvetica findfont 7.6 scalefont setfont
                {MARGIN_LEFT + 10} {cur_y} moveto ({self._esc(sl)}) show
                grestore
                """
                self.add_raw(ps_sl)
                cur_y -= 10

        self.current_y -= (box_h + 6)

    def draw_objection_row(self, objection: str, rebuttal: str, tip: str = ""):
        lines = self._wrap_text(rebuttal, 8.0, CONTENT_WIDTH - 24)
        tip_lines = self._wrap_text(tip, 7.5, CONTENT_WIDTH - 24) if tip else []
        row_h = 24 + len(lines) * 11 + (len(tip_lines) * 9.5 + 4 if tip_lines else 0)
        self.ensure_space(row_h + 8)
        self.current_y -= 3
        y = self.current_y

        ps = f"""
        gsave
        0.98 0.98 0.99 setrgbcolor
        {MARGIN_LEFT} {y - row_h} {CONTENT_WIDTH} {row_h} rectfill
        0.85 0.87 0.90 setrgbcolor
        {MARGIN_LEFT} {y - row_h} {CONTENT_WIDTH} {row_h} rectstroke
        
        0.85 0.22 0.15 setrgbcolor
        {MARGIN_LEFT} {y - row_h} 3.5 {row_h} rectfill
        
        /Helvetica-Bold findfont 8.2 scalefont setfont
        0.85 0.22 0.15 setrgbcolor
        {MARGIN_LEFT + 10} {y - 11} moveto ({self._esc(f"OBJECTION: \"{objection}\"")}) show
        
        0.10 0.52 0.25 setrgbcolor
        /Helvetica-Bold findfont 7.5 scalefont setfont
        450 {y - 11} moveto (REBUTTAL) show
        grestore
        """
        self.add_raw(ps)

        cur_y = y - 23
        for l in lines:
            ps_l = f"""
            gsave
            0.12 0.15 0.20 setrgbcolor
            /Helvetica findfont 8.0 scalefont setfont
            {MARGIN_LEFT + 10} {cur_y} moveto ({self._esc(l)}) show
            grestore
            """
            self.add_raw(ps_l)
            cur_y -= 11

        if tip_lines:
            cur_y -= 1
            for tl in tip_lines:
                ps_tl = f"""
                gsave
                0.85 0.40 0.05 setrgbcolor
                /Helvetica-Oblique findfont 7.5 scalefont setfont
                {MARGIN_LEFT + 10} {cur_y} moveto ({self._esc(tl)}) show
                grestore
                """
                self.add_raw(ps_tl)
                cur_y -= 9.5

        self.current_y -= (row_h + 5)

    def draw_box_text(self, title: str, text: str, border_color=(0.10, 0.55, 0.30)):
        lines = self._wrap_text(text, 8.0, CONTENT_WIDTH - 24)
        box_h = 24 + len(lines) * 11
        self.ensure_space(box_h + 10)
        self.current_y -= 4
        y = self.current_y
        r, g, b = border_color

        ps = f"""
        gsave
        0.96 0.99 0.96 setrgbcolor
        {MARGIN_LEFT} {y - box_h} {CONTENT_WIDTH} {box_h} rectfill
        
        {r} {g} {b} setrgbcolor
        {MARGIN_LEFT} {y - box_h} {CONTENT_WIDTH} {box_h} rectstroke
        {MARGIN_LEFT} {y - box_h} 3.5 {box_h} rectfill
        
        /Helvetica-Bold findfont 8.2 scalefont setfont
        {r} {g} {b} setrgbcolor
        {MARGIN_LEFT + 10} {y - 12} moveto ({self._esc(title)}) show
        grestore
        """
        self.add_raw(ps)

        cur_y = y - 24
        for l in lines:
            ps_l = f"""
            gsave
            0.12 0.15 0.20 setrgbcolor
            /Helvetica findfont 8.0 scalefont setfont
            {MARGIN_LEFT + 10} {cur_y} moveto ({self._esc(l)}) show
            grestore
            """
            self.add_raw(ps_l)
            cur_y -= 11

        self.current_y -= (box_h + 6)

    def draw_two_column_comparison(self, left_title: str, left_items: list[str], right_title: str, right_items: list[str]):
        col_w = (CONTENT_WIDTH - 12) / 2
        max_items = max(len(left_items), len(right_items))
        box_h = 22 + max_items * 13
        self.ensure_space(box_h + 10)
        self.current_y -= 4
        y = self.current_y

        # Left box (Red / Don't)
        ps_l = f"""
        gsave
        0.99 0.96 0.96 setrgbcolor
        {MARGIN_LEFT} {y - box_h} {col_w} {box_h} rectfill
        0.88 0.70 0.70 setrgbcolor
        {MARGIN_LEFT} {y - box_h} {col_w} {box_h} rectstroke
        0.85 0.20 0.15 setrgbcolor
        {MARGIN_LEFT} {y - box_h} 3 {box_h} rectfill
        /Helvetica-Bold findfont 8.0 scalefont setfont
        0.85 0.20 0.15 setrgbcolor
        {MARGIN_LEFT + 8} {y - 12} moveto ({self._esc(left_title)}) show
        grestore
        """
        self.add_raw(ps_l)

        # Right box (Green / Do)
        right_x = MARGIN_LEFT + col_w + 12
        ps_r = f"""
        gsave
        0.96 0.99 0.96 setrgbcolor
        {right_x} {y - box_h} {col_w} {box_h} rectfill
        0.70 0.88 0.70 setrgbcolor
        {right_x} {y - box_h} {col_w} {box_h} rectstroke
        0.10 0.55 0.25 setrgbcolor
        {right_x} {y - box_h} 3 {box_h} rectfill
        /Helvetica-Bold findfont 8.0 scalefont setfont
        0.10 0.55 0.25 setrgbcolor
        {right_x + 8} {y - 12} moveto ({self._esc(right_title)}) show
        grestore
        """
        self.add_raw(ps_r)

        # Left items
        cur_y = y - 24
        for item in left_items:
            ps_item = f"""
            gsave
            0.20 0.20 0.25 setrgbcolor
            /Helvetica findfont 7.5 scalefont setfont
            {MARGIN_LEFT + 8} {cur_y} moveto ({self._esc("x  " + item)}) show
            grestore
            """
            self.add_raw(ps_item)
            cur_y -= 13

        # Right items
        cur_y = y - 24
        for item in right_items:
            ps_item = f"""
            gsave
            0.15 0.20 0.15 setrgbcolor
            /Helvetica findfont 7.5 scalefont setfont
            {right_x + 8} {cur_y} moveto ({self._esc("+  " + item)}) show
            grestore
            """
            self.add_raw(ps_item)
            cur_y -= 13

        self.current_y -= (box_h + 6)

    def draw_formula_banner(self, text: str):
        self.ensure_space(38)
        self.current_y -= 3
        y = self.current_y
        ps = f"""
        gsave
        0.106 0.212 0.365 setrgbcolor
        {MARGIN_LEFT} {y - 28} {CONTENT_WIDTH} 28 rectfill
        0.90 0.45 0.10 setrgbcolor
        {MARGIN_LEFT} {y - 28} 3.5 28 rectfill
        /Helvetica-Bold findfont 8.5 scalefont setfont
        1.0 1.0 1.0 setrgbcolor
        {MARGIN_LEFT + 12} {y - 18} moveto ({self._esc(text)}) show
        grestore
        """
        self.add_raw(ps)
        self.current_y -= 34

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


def build_calling_sheet_ps(w: CallingSheetPSWriter):
    # PAGE 1: HEADER, STAFF, OWNER HOOK, SITUATIONS 3, 4, 5, 6
    w.draw_header_banner(
        title="MALIKAXIOM — FINAL COLD CALLING SCRIPT & CHEAT SHEET",
        subtitle="Call ke waqt bas isi flow ko follow karna hai — Extra theory zero.",
        badge="Target: 50 Calls -> WhatsApp Demos -> Follow-ups -> Paid Clients | +92 313 0466400",
    )

    w.draw_section_heading("1. STAFF / RECEPTIONIST UTHAYE")
    w.draw_dialogue(
        speaker="Agent Opening",
        text="\"Assalam-o-Alaikum! Main Haider baat kar raha hoon MalikAxiom Technology se. Mujhe [Business Name] ke owner ya marketing person se 30 seconds baat karni thi, online orders aur digital setup ke hawale se. Kya woh available hain?\"",
        subtext="Agar pooche 'Kis silsile mein?': \"Actually unki Google listing/business presence dekhi thi. Ek quick digital growth opportunity discuss karni thi. Agar possible ho to call transfer kar dein, ya unka WhatsApp number mil sakta hai?\""
    )

    w.draw_section_heading("2. OWNER PHONE UTHAYE (CORE CALL FLOW)")
    w.draw_dialogue(
        speaker="Opening (10 Seconds)",
        text="\"Assalam-o-Alaikum Sir/Ma'am, Haider baat kar raha hoon MalikAxiom Technology se. Aapka [Business Name] Google/Instagram par dekha tha. Collection/business setup kaafi acha laga. Sir bas 30 seconds ki quick baat thi.\""
    )
    w.draw_dialogue(
        speaker="The Pitch & Solution",
        text="\"Hum local businesses ko online orders aur customer handling ke liye digital setup provide karte hain. Aapka current setup dekha to laga ke ek simple website/catalog aur direct WhatsApp ordering se customers ke liye ordering aur easy ho sakti hai.\""
    )
    w.draw_dialogue(
        speaker="CTA & Follow-Up Lock",
        text="\"Main aapko WhatsApp par ek 15-second ka demo bhej doon? Aap free time mein dekh lena, phir agar relevant laga to 2 minute baat kar lenge.\"",
        subtext="Agar 'haan' bole: \"Perfect Sir. Yehi WhatsApp number hai na? Main abhi send karta hoon. Aur main kal [time] ke around ek quick follow-up kar loon?\""
    )

    w.draw_section_heading("3. SITUATION SCRIPTS (BUSINESS TYPE KE MUTABIQ)")
    w.draw_dialogue(
        speaker="Agar Business ki Website Nahi Hai",
        text="\"Sir aapki Google presence dekhi thi. Abhi dedicated mobile website/catalog nazar nahi aaya. Hum businesses ke liye ek clean mobile website banate hain jahan customer products/services dekh kar direct WhatsApp se inquiry ya order kar sakta hai. Main aapko ek 15-second sample WhatsApp kar doon? Aap dekh lena ke kaisa lagega.\""
    )
    w.draw_dialogue(
        speaker="Boutique / Clothing / Instagram Business",
        text="\"Aapka Instagram collection kaafi acha hai. Sir ek quick observation thi — agar customer ko products dekhne, price check karne aur order karne ke liye DMs mein manually baat karni pade to process thora slow ho jata hai. Hum ek mobile online store bana dete hain jahan customer directly order place kar sakta hai (COD + WhatsApp). Main ek short demo WhatsApp kar doon?\""
    )

    # PAGE 2: WEBSITES, CLINICS, OBJECTION VAULT, WHATSAPP TEMPLATE
    w.new_page()
    w.draw_dialogue(
        speaker="Existing Website Hai (Outdated / Slow)",
        text="\"Sir aapki website check ki thi. Main specifically mobile experience aur customer ordering flow dekh raha tha. Kuch areas hain jahan website ko faster aur more conversion-focused banaya ja sakta hai. Main aapko 2-3 quick points WhatsApp par share kar doon? Aap dekh lena.\""
    )
    w.draw_dialogue(
        speaker="Clinic / Doctor / Healthcare",
        text="\"Assalam-o-Alaikum Doctor Sahab. Haider from MalikAxiom Technology. Aapki clinic profile dekhi thi. Hum clinics ke liye online appointment booking aur WhatsApp-based reminders setup karte hain taake patient direct slot request kare aur staff ki manual call handling kam ho jaye. Main short demo WhatsApp kar doon?\""
    )

    w.draw_section_heading("4. MOST IMPORTANT OBJECTION REPLIES (HAR JAWAB TAYYAR)")
    
    w.draw_objection_row(
        objection="Humein zaroorat nahi.",
        rebuttal="\"Bilkul Sir, agar current setup smoothly chal raha hai to that's good. Main koi commitment nahi maang raha. Sirf ek 15-second sample dekh lein. Agar relevant lage to phir baat kar lenge.\""
    )
    w.draw_objection_row(
        objection="WhatsApp par details bhej dein.",
        rebuttal="\"Bilkul Sir. Main abhi isi number par demo aur short portfolio bhej raha hoon. Aapka naam [Name] hi hai na? Main kal [time] par ek quick follow-up kar loon?\"",
        tip="Note: Ye GOOD sign hai! Kabhi sirf 'okay' keh kar call disconnect mat karo. Follow-up time lock karo."
    )
    w.draw_objection_row(
        objection="Kitne ka hai?",
        rebuttal="\"Sir setup requirement par depend karta hai. Basic digital setup usually 10-20k range mein hota hai. Main pehle aapko relevant demo dikha deta hoon, phir exact requirement ke according price bata dunga.\""
    )
    w.draw_objection_row(
        objection="Budget nahi hai.",
        rebuttal="\"Samajh sakta hoon Sir. Isi liye hum small businesses ke liye simple packages rakhte hain. Pehle demo dekh lein, agar aapko value lage tabhi aage discuss karenge.\""
    )
    w.draw_objection_row(
        objection="Already developer hai.",
        rebuttal="\"Bohat achi baat hai Sir. Hum replace karne ke liye nahi keh rahe. Aap sirf hamara setup dekh lein. Agar koi useful feature lage to aap apne existing developer se bhi implement karwa sakte hain.\""
    )
    w.draw_objection_row(
        objection="Busy hoon / Drive kar raha hoon.",
        rebuttal="\"Sure Sir, bilkul. Main WhatsApp par short demo bhej deta hoon. Aap bata dein kal 11 baje ya 3 baje kis time 2 minute ke liye convenient rahega?\""
    )
    w.draw_objection_row(
        objection="Interested nahi hoon.",
        rebuttal="\"No issue Sir, completely understand. Main disturb nahi karunga. Agar future mein online ordering ya website ki requirement ho to aap hamara WhatsApp save kar sakte hain. Thank you for your time.\"",
        tip="Respectfully exit without arguing."
    )

    # PAGE 3: WHATSAPP TEMPLATE, FOLLOW-UP SCRIPT, DOS & DON'TS, TARGET
    w.new_page()
    w.draw_section_heading("5. POST-CALL WHATSAPP MESSAGE (CALL KE FORAN BAAD)")
    w.draw_box_text(
        title="Immediate WhatsApp Template",
        text="Assalam-o-Alaikum Sir, Haider from MalikAxiom Technology here. As discussed, yeh short demo/sample hai jo aapke business ke liye online presence, product catalog aur direct WhatsApp ordering ka concept show karta hai.\n\n"
             "🎥 Demo: [LINK]\n"
             "Aap jab free hon 30 seconds dekh lijiyega. Main [DAY/TIME] par aapko quick follow-up kar leta hoon.\n\n"
             "Thank you! Haider | MalikAxiom Technology | WhatsApp: 0313 0466400"
    )

    w.draw_section_heading("6. FOLLOW-UP CALL (NEXT DAY SCRIPT)")
    w.draw_dialogue(
        speaker="Next Day Follow-Up",
        text="\"Assalam-o-Alaikum Sir, Haider from MalikAxiom. Kal maine aapko WhatsApp par [Business Name] ka short demo bheja tha. Sir kya aapko dekhne ka chance mila?\"",
        subtext="Agar dekha: \"Great Sir! Aapko concept kaisa laga? Phir hum aapke business ke according exact setup discuss kar lete hain. Aaj [time] convenient hai ya kal?\"\n"
                "Agar nahi dekha: \"Koi issue nahi Sir. Main WhatsApp par ek baar phir send kar deta hoon. Sirf 30 seconds ka demo hai. Aap dekh kar bata dijiyega.\""
    )

    w.draw_section_heading("7. CALL KA GOLDEN FORMULA & CHECKLIST")
    w.draw_formula_banner("GOLDEN 6 STEPS:  1. Salam  ->  2. Observation  ->  3. Opportunity  ->  4. Solution  ->  5. Demo CTA  ->  6. Time Lock")

    w.draw_two_column_comparison(
        left_title="YE MAT KARO (STRICT NO)",
        left_items=[
            "Company ki 2-minute lambi history",
            "Apni skills ki long list sunana",
            "'Hum best agency hain' claim karna",
            "Bohat technical terms use karna",
            "Customer ko force ya argue karna",
            "Fake statistics bolna",
            "Pehli call par detailed proposal",
        ],
        right_title="YE KARO (BEST PRACTICES)",
        right_items=[
            "Sirf customer ke business ki baat",
            "Customer ke direct benefit ki baat",
            "Short sentences & active listening",
            "Natural conversational Urdu-English",
            "15-second WhatsApp Demo bhejna",
            "Follow-up appointment time lock karna",
            "Target: 50 calls daily quota complete",
        ]
    )

    w.draw_formula_banner("TUMHARA ACTUAL TARGET: 50 Calls -> Conversations -> Demos -> Follow-ups -> Meetings -> PAID CLIENT!")


def main():
    writer = CallingSheetPSWriter()
    build_calling_sheet_ps(writer)
    ps_output = writer.render_all()

    project_root = Path(__file__).resolve().parent.parent
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True, parents=True)

    ps_path = output_dir / "MalikAxiom_Final_Calling_Sheet.ps"
    pdf_path = output_dir / "MalikAxiom_Final_Calling_Sheet.pdf"

    ps_path.write_text(ps_output, encoding="utf-8")
    print(f"PostScript written: {ps_path}")

    cmd = ["ps2pdf", str(ps_path), str(pdf_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and pdf_path.exists():
        print(f"✅ Final Calling Sheet PDF created: {pdf_path} ({pdf_path.stat().st_size} bytes)")
        if ps_path.exists():
            ps_path.unlink()
    else:
        print(f"Error compiling PDF: {res.stderr}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
