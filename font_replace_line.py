import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import os

def recolor(old):
    """Convet sRGB color back to PDF color triple.
    sRGB is an integer of format RRGGBB.
    """
    r = old >> 16
    g = (old - (r << 16)) >> 8
    b = old - (r << 16) - (g << 8)
    return (r / 255, g / 255, b / 255)


def resize(span, font):
    """Adjust fontsize for using replacement font."""
    text = span["text"]
    rect = fitz.Rect(span["bbox"])
    fsize = span["size"]
    tl = font.text_length(text, fontsize=fsize)
    new_size = rect.width / tl * fsize
    return new_size
    

def replace_font_try2(pdf_path, output_path, font_name):
    # page의 font를 변경하는 방법
    # Text bbox가 변경되지 않아 문제 발생 > Text bbox를 변경하려면 text를 수정해야 하는데, 이는 불가능
    indoc = fitz.open(pdf_path)

    font = fitz.Font(font_name)
    font_buffer = font.buffer

    for page_num in range(indoc.page_count): 
        page = indoc[page_num]
        page.insert_font(fontname=font_name, fontbuffer=font_buffer)
        cont = bytearray(page.read_contents())

        font_xrefs = {}
        for f in page.get_fonts():
            font_xrefs[f[0]] = f[4] # font_xrefs [xref] = fontname

        for xref in font_xrefs.keys():
            if font_xrefs[xref] != font_name:
                prev_name =  b"/" + font_xrefs[xref].encode() + b" "
                new_name = b"/" + font_name.encode() + b" "
                cont = cont.replace(prev_name, new_name)
        xref = page.get_contents()[0]
        page.parent.update_stream(xref, cont)
        page.set_contents(xref)
        page.clean_contents(sanitize=True)

    # Save the modified PDF
    indoc.save(output_path, garbage=4, deflate=False)


def cont_clean(page, fontrefs):
    """Remove text written with one of the fonts to replace.

    Args:
        page: the page
        fontrefs: dict of contents stream xrefs. Each xref key has a list of
            ref names looking like b"/refname ".
    """

    def remove_font(fontrefs, lines):
        """This inline function removes references to fonts in a /Contents stream.

        Args:
            fontrefs: a list of bytes objects looking like b"/fontref ".
            lines: a list of the lines of the /Contents.
        Returns:
            (bool, lines), where the bool is True if we have changed any of
            the lines.
        """
        changed = False
        count = len(lines)
        for ref in fontrefs:
            found = False  # switch: processing our font
            for i in range(count):
                if lines[i] == b"ET":  # end text object
                    found = False  # no longer in found mode
                    continue
                if lines[i].endswith(b" Tf"):  # font invoker command
                    if lines[i].startswith(ref):  # our font?
                        found = True  # switch on
                        lines[i] = b""  # remove line
                        changed = True  # tell we have changed
                        continue  # next line
                    else:  # else not our font
                        found = False  # switch off
                        continue  # next line
                if found == True and (
                    lines[i].endswith(
                        (
                            b"TJ",
                            b"Tj",
                            b"TL",
                            b"Tc",
                            b"Td",
                            b"Tm",
                            b"T*",
                            b"Ts",
                            b"Tw",
                            b"Tz",
                            b"'",
                            b'"',
                        )
                    )
                ):  # write command for our font?
                    lines[i] = b""  # remove it
                    changed = True  # tell we have changed
                    continue
        return changed, lines

    doc = page.parent
    xref_list = []
    for xref in fontrefs.keys():
        xref0 = 0 + xref
        if xref0 == 0:  # the page contents
            #xref0 = page.get_contents()[0]  # there is only one /Contents obj now
            xref_list += [(xref,i) for i in page.get_contents()]
        else:
            xref_list.append((xref,xref0))
    
    for (xref, xref0) in xref_list: 
        cont = doc.xref_stream(xref0)
        cont_lines = cont.splitlines()
        changed, cont_lines = remove_font(fontrefs[xref], cont_lines)
        if changed:
            cont = b"\n".join(cont_lines) + b"\n"
            doc.update_stream(xref0, cont)  # replace command source


def get_page_fontrefs(page, font_name):
    fontlist = page.get_fonts(full=True)
    # Ref names for each font to replace.
    # Each contents stream has a separate entry here: keyed by xref,
    # 0 = page /Contents, otherwise xref of XObject
    fontrefs = {}
    for f in fontlist:
        fontname = f[3]
        cont_xref = f[-1]  # xref of XObject, 0 if page /Contents
        idx = fontname.find("+") + 1
        fontname = fontname[idx:]  # remove font subset indicator
        if fontname != font_name:  # we replace this font!
            refname = f[4]
            refname = b"/" + refname.encode() + b" "
            refs = fontrefs.get(cont_xref, [])
            refs.append(refname)
            fontrefs[cont_xref] = refs
    return fontrefs  # return list of font reference names


def replace_font(pdf_path, output_path, font_name):
    indoc = fitz.open(pdf_path)
    extr_flags = fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE
    font = fitz.Font(font_name)

    for page in indoc:
            # extract text again
            blocks = page.get_text("dict", flags=extr_flags)["blocks"]

            # clean contents streams of the page and any XObjects.
            #page.clean_contents(sanitize=True)
            fontrefs = get_page_fontrefs(page, font_name)
            if fontrefs == {}:  # page has no fonts to replace
                continue
            cont_clean(page, fontrefs)  # remove text using fonts to be replaced
            textwriters = {}  # contains one text writer per detected text color

            for block in blocks:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].replace(chr(0xFFFD), chr(0xB6))
                        # guard against non-utf8 characters
                        textb = text.encode("utf8", errors="backslashreplace")
                        text = textb.decode("utf8", errors="backslashreplace")
                        span["text"] = text
                        color = span["color"]  # make or reuse textwriter for the color
                        if color in textwriters.keys():  # already have a textwriter?
                            tw = textwriters[color]  # re-use it
                        else:  # make new
                            tw = fitz.TextWriter(page.rect)  # make text writer
                            textwriters[color] = tw  # store it for later use
                        try:
                            tw.append(
                                span["origin"],
                                text,
                                font=font,
                                fontsize=resize(span, font),  # use adjusted fontsize
                                #fontsize = span["size"],
                            )
                        except:
                            print("page %i exception:" % page.number, text)

            # now write all text stored in the list of text writers
            for color in textwriters.keys():  # output the stored text per color
                tw = textwriters[color]
                outcolor = fitz.sRGB_to_pdf(color)  # recover (r,g,b)
                tw.write_text(page, color=outcolor)

    indoc.save(
        output_path,
        garbage=4,
        deflate=True,
    )


def draw_bbox_pdf(pdf_path,page, output):
    # Draw bounding box of text
    doc = fitz.open(pdf_path)
    page = doc[page]
    pixmap = page.get_pixmap(dpi=300)
    image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    draw = ImageDraw.Draw(image)

    scale_x = page.rect.width / image.width
    scale_y = page.rect.height / image.height

    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    bbox = span["bbox"]
                    scaled_bbox = [bbox[0] / scale_x, bbox[1] / scale_y, bbox[2] / scale_x, bbox[3] / scale_y]
                    draw.rectangle(scaled_bbox, outline="red", width=2)
    image.save(output)


if __name__ == "__main__":

    base_path = "/shared/workspace/0516_TableTestSet/51-100/pdfs/"
    pdfs = os.listdir(base_path)
    #pdfs = ["07_2310.04799.pdf"]"

    pymupdf_font = [
    "figo", "figbo", "figit", "figbi", 
    "fimo", "fimbo", "spacemo", "spacembo", 
    "spacemit", "spacembi", "notos", "notosbi",  
    "notosbo", "ubuntu", "ubuntubo",
    "ubuntubi", "ubuntuit", "ubuntm", "ubuntmbo", 
    "ubuntmbi", "ubuntmit", "cascadia", "cascadiab", 
    "cascadiai", "cascadiabi"]

    base_font = [
    'courier', 'courier-oblique', 'courier-bold', 'courier-boldoblique', 
    'helvetica', 'helvetica-oblique', 'helvetica-bold', 'helvetica-boldoblique', 
    'times-roman', 'times-italic', 'times-bold', 'times-bolditalic', 
    'helv', 'heit', 'hebo', 'hebi', 
    'cour', 'coit', 'cobo', 'cobi', 
    'tiro', 'tibo', 'tiit', 'tibi']

    styles = pymupdf_font + base_font
    styles = ["times-bolditalic"]

    os.makedirs("./example_line", exist_ok=True)
    for pdf in pdfs:
        pdf_path = base_path + pdf

        for font_name in styles:
            print(f"Processing [file: {pdf}] [font: {font_name}]")
            output_path = f"./example_line/{font_name}_{pdf}"
            replace_font(pdf_path, output_path, font_name)