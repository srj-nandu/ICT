from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "report_screenshots"
WIDTH = 1366
HEIGHT = 768

BG = "#f4f7f6"
INK = "#182022"
MUTED = "#667173"
TEAL = "#0f766e"
TEAL_DARK = "#0b4f4a"
TEAL_LIGHT = "#dff4f1"
CARD = "#ffffff"
LINE = "#d8e2e0"
ORANGE = "#c2410c"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


F10 = font(10)
F13 = font(13)
F14 = font(14)
F16 = font(16)
F18 = font(18, True)
F22 = font(22, True)
F30 = font(30, True)
F44 = font(44, True)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str, outline: str | None = None) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline or fill, width=1)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, fill: str = INK, face: ImageFont.ImageFont = F14) -> None:
    draw.text(xy, value, fill=fill, font=face)


def header(draw: ImageDraw.ImageDraw, active: str) -> None:
    draw.rectangle((0, 0, WIDTH, 76), fill="#ffffff")
    draw.line((0, 75, WIDTH, 75), fill=LINE, width=2)
    rounded(draw, (66, 20, 106, 58), 8, TEAL)
    text(draw, (78, 31), "CV", "#ffffff", F16)
    text(draw, (118, 18), "Careermitra", INK, F18)
    text(draw, (118, 43), "Resume matching workspace", MUTED, F13)
    nav = ["Home", "Dashboard", "Upload", "Profile", "Contact"]
    x = 648
    for item in nav:
        color = TEAL if item == active else MUTED
        text(draw, (x, 30), item, color, F14)
        x += 96
    rounded(draw, (1188, 22, 1296, 54), 16, TEAL_LIGHT, TEAL)
    text(draw, (1214, 31), "Sign in", TEAL_DARK, F13)


def save_home() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "Home")
    text(draw, (76, 128), "Resume Checker", TEAL, F16)
    text(draw, (76, 164), "Is your resume ready", INK, F44)
    text(draw, (76, 216), "for the role?", INK, F44)
    text(draw, (78, 286), "Upload a PDF resume, compare it with job-role skills,", MUTED, F18)
    text(draw, (78, 314), "and get a clear match score with missing skills and charts.", MUTED, F18)
    rounded(draw, (78, 384, 526, 568), 18, "#ffffff", LINE)
    text(draw, (112, 424), "Drop your resume here or choose a file.", INK, F18)
    text(draw, (112, 458), "PDF only. Maximum 8MB file size.", MUTED, F14)
    rounded(draw, (112, 504, 286, 548), 20, TEAL)
    text(draw, (142, 517), "Analyze Resume", "#ffffff", F14)
    rounded(draw, (680, 118, 1266, 620), 18, "#ffffff", LINE)
    rounded(draw, (724, 162, 888, 344), 14, TEAL_LIGHT, LINE)
    text(draw, (752, 194), "Resume Score", MUTED, F16)
    text(draw, (758, 238), "92/100", TEAL_DARK, F44)
    text(draw, (758, 306), "4 gaps found", ORANGE, F16)
    rounded(draw, (930, 162, 1216, 546), 14, "#f8faf9", LINE)
    text(draw, (960, 194), "CONTENT", INK, F18)
    for y, width in [(238, 210), (274, 172), (310, 228), (376, 194), (412, 240), (448, 164)]:
        rounded(draw, (960, y, 960 + width, y + 14), 7, "#d7e2e0")
    image.save(OUT / "home_page.png")


def save_upload() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "Upload")
    rounded(draw, (92, 118, 1274, 650), 18, "#ffffff", LINE)
    text(draw, (132, 154), "Upload Resume", INK, F30)
    text(draw, (132, 198), "Choose a PDF resume and one or more target job roles.", MUTED, F16)
    text(draw, (132, 258), "PDF resume", INK, F16)
    rounded(draw, (132, 288, 1234, 348), 12, "#f8faf9", LINE)
    text(draw, (158, 309), "ABINAYA_SATHEESH_KUMAR_RESUME.pdf", MUTED, F16)
    text(draw, (132, 386), "Target job roles", INK, F16)
    roles = ["Backend Developer", "Frontend Developer", "Data Analyst", "Data Scientist", "HR Executive", "Digital Marketing"]
    x, y = 132, 426
    for role in roles:
        w = 190 if len(role) < 15 else 220
        rounded(draw, (x, y, x + w, y + 44), 22, TEAL_LIGHT, TEAL)
        text(draw, (x + 20, y + 13), role, TEAL_DARK, F14)
        x += w + 18
        if x > 1060:
            x, y = 132, y + 62
    rounded(draw, (132, 570, 304, 616), 22, TEAL)
    text(draw, (164, 584), "Analyze Resume", "#ffffff", F14)
    image.save(OUT / "upload_page.png")


def save_login_register() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "Home")
    rounded(draw, (116, 128, 634, 650), 18, "#ffffff", LINE)
    text(draw, (164, 176), "Sign in", INK, F30)
    text(draw, (164, 220), "Access your dashboard and saved reports.", MUTED, F16)
    for label, y in [("Email address", 288), ("Password", 374)]:
        text(draw, (164, y), label, INK, F14)
        rounded(draw, (164, y + 28, 586, y + 82), 10, "#f8faf9", LINE)
    rounded(draw, (164, 500, 328, 546), 22, TEAL)
    text(draw, (214, 514), "Login", "#ffffff", F14)
    rounded(draw, (732, 128, 1250, 650), 18, "#ffffff", LINE)
    text(draw, (780, 176), "Create Account", INK, F30)
    text(draw, (780, 220), "Register to analyze resumes securely.", MUTED, F16)
    for label, y in [("Full name", 276), ("Email address", 356), ("Password", 436)]:
        text(draw, (780, y), label, INK, F14)
        rounded(draw, (780, y + 28, 1202, y + 82), 10, "#f8faf9", LINE)
    rounded(draw, (780, 592, 972, 638), 22, TEAL)
    text(draw, (818, 606), "Create Account", "#ffffff", F14)
    image.save(OUT / "login_register_page.png")


def save_dashboard() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "Dashboard")
    rounded(draw, (80, 112, 1286, 226), 18, TEAL)
    text(draw, (116, 142), "Dashboard", TEAL_LIGHT, F16)
    text(draw, (116, 174), "Welcome back, Sooraj", "#ffffff", F30)
    stats = [("Stored resumes", "12"), ("Profiles analyzed", "9"), ("Structured files", "36"), ("Best match", "92%")]
    x = 80
    for label, value in stats:
        rounded(draw, (x, 254, x + 282, 358), 16, "#ffffff", LINE)
        text(draw, (x + 26, 282), label, MUTED, F14)
        text(draw, (x + 26, 314), value, TEAL_DARK, F30)
        x += 308
    rounded(draw, (80, 392, 606, 674), 16, "#ffffff", LINE)
    text(draw, (112, 424), "Skill Snapshot", INK, F22)
    for i, (skill, count) in enumerate([("python", 8), ("sql", 7), ("git", 6), ("pandas", 5), ("communication", 5)]):
        y = 474 + i * 34
        text(draw, (116, y), skill, INK, F14)
        rounded(draw, (276, y + 2, 276 + count * 24, y + 16), 8, TEAL)
    rounded(draw, (638, 392, 1286, 674), 16, "#ffffff", LINE)
    text(draw, (670, 424), "Analysis History", INK, F22)
    headers = ["Resume", "Job Role", "Match", "Uploaded"]
    xs = [670, 892, 1058, 1158]
    for x, h in zip(xs, headers):
        text(draw, (x, 472), h, MUTED, F13)
    rows = [("abinaya_resume.pdf", "Data Analyst", "92%", "02 May"), ("abila_benny.pdf", "HR Executive", "74%", "02 May"), ("candidate_cv.pdf", "Backend Dev", "68%", "01 May")]
    for r, row in enumerate(rows):
        y = 510 + r * 44
        draw.line((670, y - 12, 1254, y - 12), fill=LINE, width=1)
        for x, value in zip(xs, row):
            text(draw, (x, y), value, INK if value != row[2] else TEAL, F14)
    image.save(OUT / "dashboard_page.png")


def save_result() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "Dashboard")
    rounded(draw, (80, 112, 1286, 242), 18, TEAL)
    text(draw, (118, 142), "Analysis Result", TEAL_LIGHT, F16)
    text(draw, (118, 178), "92% match", "#ffffff", F44)
    text(draw, (792, 152), "Candidate: Abinaya Satheesh Kumar", "#ffffff", F16)
    text(draw, (792, 184), "Compared with Data Analyst", TEAL_LIGHT, F16)
    rounded(draw, (80, 278, 636, 668), 16, "#ffffff", LINE)
    text(draw, (116, 314), "Skills", INK, F22)
    text(draw, (116, 360), "Extracted: python, sql, excel, pandas, numpy, matplotlib", MUTED, F14)
    text(draw, (116, 396), "Matched: python, sql, excel, pandas, numpy, matplotlib", MUTED, F14)
    text(draw, (116, 454), "Missing Skills", INK, F18)
    for i, skill in enumerate(["power bi", "tableau"]):
        rounded(draw, (116 + i * 126, 496, 218 + i * 126, 534), 18, "#fff1e8", ORANGE)
        text(draw, (138 + i * 126, 507), skill, ORANGE, F14)
    rounded(draw, (672, 278, 1286, 668), 16, "#ffffff", LINE)
    text(draw, (710, 314), "Graphs", INK, F22)
    rounded(draw, (730, 374, 846, 570), 8, TEAL)
    rounded(draw, (892, 464, 1008, 570), 8, ORANGE)
    text(draw, (742, 584), "Match", MUTED, F13)
    text(draw, (910, 584), "Gap", MUTED, F13)
    text(draw, (1072, 430), "Missing skill", MUTED, F14)
    rounded(draw, (1072, 464, 1208, 484), 10, ORANGE)
    rounded(draw, (1072, 512, 1160, 532), 10, ORANGE)
    image.save(OUT / "result_page.png")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    save_home()
    save_login_register()
    save_upload()
    save_dashboard()
    save_result()
    print(f"Wrote report screenshots to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
