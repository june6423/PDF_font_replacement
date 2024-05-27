import fitz  # PyMuPDF
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
    

def replace_font(pdf_path, output_path, font_name):
    indoc = fitz.open(pdf_path)
    pdfdata = indoc.tobytes()
    outdoc = fitz.open("pdf", pdfdata)

    font = fitz.Font(font_name)
    #    font_buffer = font.buffer

    for page_num in range(outdoc.page_count): 
        page = outdoc[page_num]
        # page.insert_font(fontname=font_name, fontbuffer=font_buffer)
        # print(page_num, page.get_fonts())
        blocks = page.get_text("dict")["blocks"] 
        for block in blocks: 
            if "lines" in block: 
                for line in block["lines"]: 
                    for span in line["spans"]: 
                        bbox = span["bbox"] 
                        rect = fitz.Rect(bbox) 
                        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1)) 
 
    for page_num in range(len(indoc)):
        inpage = indoc[page_num]
        alltext = inpage.get_text("dict")

        for block in alltext["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    color = span["color"]
                    new_fontsize = resize(span, font)
                    # Use insert_text to draw the text with the new font and color
                    outdoc[page_num].insert_text(
                        fitz.Rect(span["bbox"]).bl,
                        span["text"],
                        fontname=font_name,
                        fontsize=new_fontsize,
                        color=recolor(color),
                    )

    # Save the modified PDF
    outdoc.save(output_path, garbage=4, deflate=False)

if __name__ == "__main__":

    base_path = "/shared/workspace/0516_TableTestSet/51-100/pdfs/"
    pdfs = os.listdir(base_path)
    #pdfs = ["07_2310.04799.pdf"]

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

    os.makedirs("./example_patch", exist_ok=True)
    for pdf in pdfs:
        pdf_path = base_path + pdf

        for font_name in styles:
            print(f"Processing [file: {pdf}] [font: {font_name}]")
            output_path = f"./example_patch/{font_name}_{pdf}"
            replace_font(pdf_path, output_path, font_name)
