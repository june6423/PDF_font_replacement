import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import os
import random

def random_font():
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

    font_list = pymupdf_font + base_font
    #choose random font in font_list
    return font_list[random.randint(0, len(font_list)-1)]


def get_dpi(indoc, orig_W, orig_H):
    """Get the DPI of the PDF page."""

    page = indoc[0]
    page_H = page.rect.height
    page_W = page.rect.width

    dpi_x = 72 * orig_W / page_W
    dpi_y = 72 * orig_H / page_H

    return round((dpi_x + dpi_y) / 2)


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
    
    
def tilted_span(page, wdir, word, font):
    """Output a non-horizontal text span."""
    cos, sin = wdir  # writing direction from the line
    matrix = fitz.Matrix(cos, -sin, sin, cos, 0, 0)  # corresp. matrix
    text = word["text"]  # text to write
    bbox = fitz.Rect(word["bbox"])
    fontsize = word["size"]  # adjust fontsize
    tl = font.text_length(text, fontsize)  # text length with new font
    m = max(bbox.width, bbox.height)  # must not exceed max bbox dimension
    if tl > m:
        fontsize *= m / tl  # otherwise adjust
    opa = 0.1 if fontsize > 100 else 1  # fake opacity for large fontsizes
    tw = fitz.TextWriter(page.rect, opacity=opa, color=fitz.sRGB_to_pdf(word["color"]))
    origin = fitz.Point(word["origin"])
    if sin > 0:  # clockwise rotation
        origin.y = bbox.y0
    tw.append(origin, text, font=font, fontsize=fontsize)
    tw.write_text(page, morph=(origin, matrix))


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
                #if lines[i].endswith(b" Tf"):  # font invoker command
                if lines[i].startswith(b"/"):
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
        if len(cont_lines) == 0 or cont_lines[0] == cont:
            return False
        changed, cont_lines = remove_font(fontrefs[xref], cont_lines)
        if changed:
            cont = b"\n".join(cont_lines) + b"\n"
            doc.update_stream(xref0, cont)  # replace command source
    return True


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


def process(indoc, page_num, bbox, font_name, dpi=300):
    assert isinstance(indoc, fitz.Document)
    assert isinstance(page_num, int)
    assert isinstance(font_name, str)

    if font_name == "random":
        font_name = random_font()

    extr_flags = fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE
    font = fitz.Font(font_name)
    page = indoc[page_num]
    blocks = page.get_text("rawdict", flags=extr_flags)["blocks"]

    fontrefs = get_page_fontrefs(page, font_name)
    if fontrefs == {}:  # page has no fonts to replace
        print("Given PDF does not contain any fonts", page_num)
        return None
    
    valid = cont_clean(page, fontrefs)  # remove text using fonts to be replaced
    if not valid:
        print("Cannot process this file.")
        return None
    
    textwriters = {}  # contains one text writer per detected text color

    for block in blocks:
        for line in block["lines"]:
            wmode = line["wmode"] # writing mode (horizontal, vertical)
            wdir = list(line["dir"]) # writing direction
            for span in line["spans"]:
                span_char = span['chars']

                word_list = []
                for character in span_char:
                    if character['c'].isspace():
                        word_list.append({'bbox': fitz.Rect(0,0,0,0),
                                            'text': '', 'origin': None,
                                            'color': span['color'], 
                                            'size': span['size']})
                    else:
                        if not word_list:
                            word_list.append({'bbox': fitz.Rect(character['bbox']), 
                                            'text': character['c'], 
                                            'origin': character['origin'], 
                                            'color': span['color'], 
                                            'size': span['size']})
                        else:
                            if word_list[-1]['origin'] is None:
                                word_list[-1]['origin'] = character['origin']
                            word_list[-1]['bbox'] = fitz.Rect(character['bbox']) | word_list[-1]['bbox']
                            word_list[-1]['text'] += character['c']
                word_list_cleaned = [word for word in word_list if word['origin'] is not None]

                for word in word_list_cleaned:
                    text = word["text"].replace(chr(0xFFFD), chr(0xB6))
                    # guard against non-utf8 characters
                    textb = text.encode("utf8", errors="backslashreplace")
                    text = textb.decode("utf8", errors="backslashreplace")

                    if wdir != [1, 0]:  # special treatment for tilted text
                        tilted_span(page, wdir, word, font)
                        continue

                    if word['color'] in textwriters.keys():  # already have a textwriter?
                        tw = textwriters[word['color']]  # re-use it
                    else:  # make new
                        tw = fitz.TextWriter(page.rect)  # make text writer
                        textwriters[word['color']] = tw  # store it for later use
                    try:
                        tw.append(
                            word["origin"],
                            text,
                            font=font,
                            fontsize=min(span['size'],resize(word, font)),  # use adjusted fontsize
                        )
                    except:
                        print("page %i exception:" % page.number, text)

    # now write all text stored in the list of text writers
    for color in textwriters.keys():  # output the stored text per color
        tw = textwriters[color]
        outcolor = fitz.sRGB_to_pdf(color)  # recover (r,g,b)
        tw.write_text(page, color=outcolor)

    # Crop the image
    pixmap = indoc[page_num].get_pixmap(dpi=dpi)
    image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    image = image.crop(bbox)
    return image


def replace_font(indoc, page_num, bbox, font_name, dpi): 
    """Replace font in a PDF page"""

    # indoc: input PDF document
    # page_num: page number to replace font
    # bbox: The bounding box to crop the image (x1, y1, x2, y2)
    # font_name: font name to replace
    # dpi: resolution of the output image (bbox must be specified in the same resolution as dpi). 
    # If you dont know the dpi, you can use get_dpi function to get the dpi of the page.
    # output: A cropped PIL image of the specified page and bounding box.

    if isinstance(page_num, int):
        return process(indoc, page_num, bbox, font_name, dpi)
    
    elif isinstance(page_num, list):
        return_list = []
        for page in page_num:
            return_list.append(process(indoc, page, bbox, font_name, dpi))
        return return_list
    


# import fitz, json
# path = "/shared/workspace/0516_TableTestSet/51-100/pdfs/4.pdf"
# json_path = "/shared/workspace/0516_TableTestSet/51-100/fixjson/4.json"
# indoc = fitz.open(path)
# with open(json_path, "r") as f:
#     data = json.load(f)
# bbox = data['bbox'] # [155,2751,2237,2978]
# image = replace_font(indoc, 13, bbox, "times-bolditalic", 288)
# image.save("/shared/workspace/p.png")