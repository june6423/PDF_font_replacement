# Replacing Fonts in a PDF

This project supports an easy way to replace the font of a PDF document. (requires PyMuPdf v1.24.4) All our work is referenced from PyMuPdf-Utilities GitHub, but since it's out of date, we've fixed a few errors. 

You can find many examples and technical background on PyMuPdf_Utilities Official GitHub.
https://github.com/pymupdf/PyMuPDF-Utilities


## Features

It supports the following features:

* Replaces **EVERY** fonts in a PDF to target font
* Keeps tables of contents, annotations, links, images, etc. in place
* Rewrites selected text with a new font maintaining the original layout as closely as possible. (Including tilt)
* Resizes the font so that the **bbox of each word doesn't change**, so there's no overlapping text. 
## How to use

```
from util import replace_font
doc = fitz.open(pdf_path)
image = replace_font(doc, page_num, bbox, font_name, dpi)
```

This function returns a cropped PIL Image of the specified page and bbox with font changed.   
The ```font_name``` can be one of the supported fonts, or you can specify ```font_name = "random"``` to select a random font.
Make sure your **```bbox``` format is (x1, y1, x2, y2) and it aligns with specified ```dpi```.**   
The ```dpi``` determines the resolution of the target image and is used to crop the correct bbox.  
If you don't know the dpi, you can calculate it using the ```get_dpi()``` function and the coordinates of the entire PDF page that you used to calculate the bbox coordinates.  


```
doc = fitz.open(pdf_path)
dpi = get_dpi(pdf_path, page_width, page_height)
```


## Supported Fonts

This project does not support every font.   
To replace every text in PDF, We must use a well-known font that contains every glyph and Unicode.  
Here's a list of supported fonts in this project.

```
pymupdf_font = [
    "figo", "figbo", "figit", "figbi", 
    "fimo", "fimbo", "spacemo", "spacembo", 
    "spacemit", "spacembi", "notos", "notosbi",  
    "notosbo", "ubuntu", "ubuntubo",
    "ubuntubi", "ubuntuit", "ubuntm", "ubuntmbo", 
    "ubuntmbi", "ubuntmit", "cascadia", "cascadiab", 
    "cascadiai", "cascadiabi"] # 25 Fonts in PyMuPDF Default Font

base_font = [
    'courier', 'courier-oblique', 'courier-bold', 'courier-boldoblique', 
    'helvetica', 'helvetica-oblique', 'helvetica-bold', 'helvetica-boldoblique', 
    'times-roman', 'times-italic', 'times-bold', 'times-bolditalic', 
    'helv', 'heit', 'hebo', 'hebi', 
    'cour', 'coit', 'cobo', 'cobi', 
    'tiro', 'tibo', 'tiit', 'tibi'] # 24 Fonts in PDF Base Font
```


## Limitations

While this is a set of useful scripts providing a long-awaited feature, it is not a "silver bullet" and does have its limitations and shortcomings.

1. **REPLACEMENT might fail for some PDF documents**. This project extracts page content using ```doc.xref_stream()```. Extracted contents are expected to be separated with the newline character "\n". Some documents are not separated by "\n", which causes the text in existing fonts to fail to clear. This project will return None if unseparated documents are detected..

2. **It might fail to restore some special characters**. SSome PDF documents unusually store special characters. There is a mismatch between the visual representation of the special character and Unicode, making it impossible to restore the special character. This is a problem with PDF documents, and there is no silver bullet to fix it.

3. **Font size and white space between words could change**. This project resizes the font to preserve the word bbox, so non-overlapping is guaranteed.

4. **Do not expect** that the text in the formula remains clear!

5. It cannot replace the font of the footnote. 


## Previous Approach and Ablation

In our first attempt, we used a white patch to cover the existing text and tried to overwrite the new text on top. However, this method obscured the background and resulted in the generated PDF containing two duplicate pieces of text.

Next, we modified the PDF file content stream directly. We based our work on PyMuPDF-Utilities' font replacement, where the existing logic resizes the internal font in a way that respects the bounding box (bbox) of a line of text. Preserving the bboxes of words and lines each has its own advantages and disadvantages. You can modify the ```mode = "word"``` in ```util.replace_font()``` to change the logic.

The code for the first attempt is in ```font_replace_patch.py```, and the code for the line logic is in ```font_replace_line.py```. The code for the word logic is in ```font_replace_word.py```. The code and example files will give you an idea of the quality of each version and their respective pros and cons.
