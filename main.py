import argparse
import math
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
import ebooklib
from ebooklib import epub
import openai
from tqdm import tqdm

# CONFIG_PATH = Path.home() / '.tinybooks'

MIN_NUM_CHARS_TO_SUMMARIZE = 100


PROMPT_WITHOUT_IMAGE = """
Please shorten this paragraph to about {num_words} words. 
Please try to keep the original structure as much as possible. Please also try to keep the original style and tone. 
You can skip the part that is not important. Allocate words wisely on the important things.

```
{text}
```

ONLY output the shortened paragraph. Do not output anything else.
"""

SYSTEM_PROMPT_WITH_IMAGE = """
You must keep ALL the images in the shortened version. The images are not counted in the word limit.
"""

PROMPT_WITH_IMAGE = """
# Instructions
Please shorten this paragraph to about {num_words} words. 
Please try to keep the original structure as much as possible. Please also try to keep the original style and tone. 
You can skip the part that is not important. Allocate words wisely on the important things.
Keep the <img/> tags in the shortened version. Put them in suitable locations

# Example
## Input
As the sun dipped below the horizon, casting a warm orange glow across the tranquil lake, <img src="image01_sunset.jpg"/> Sarah couldn't help but feel a sense of serenity wash over her. The gentle ripples on the water's surface mirrored the calmness she found within herself. A light breeze rustled the leaves of the tall trees that lined the shore, creating a soothing symphony of nature's whispers. It was moments like these when she felt most connected to the world around her, a reminder of the beauty that could be found in the simplest of moments.
## Output
As the sun set over the lake, <img src="image01_sunset.jpg"/> Sarah felt serene, with ripples and rustling leaves creating a tranquil atmosphere.

# Text to be shortened:
```
{text}
```

# Important
In the shortened version, {imgs} MUST be contained
Do not explain or output anything other than the shortened version
"""


TOC_PROMPT = """
I am creating a shortened version of a book. Here is the table of contents. Please remove the sections that are not essential for the readers (like the preface, appendix, references, legal information, etc.). Please return a list in the same format as below but with unimportant sections removed. 

{toc}

ONLY output the list (the table of contents). DO NOT output anything else or explain.
"""



def chap2text(chap):
    soup = BeautifulSoup(chap, 'html.parser')

    elements = []
    imgs = []
    blacklist = ['[document]', 'noscript', 'header', 'html', 'meta', 'head', 'input', 'script']
    block_elements = ['p', 'div', 'br']

    for descendant in soup.descendants:
        if isinstance(descendant, NavigableString) and descendant.strip():
            if descendant.parent.name not in blacklist:
                if descendant.parent.name in block_elements:
                    elements.append("\n" + str(descendant))
                else:
                    elements.append(str(descendant))
        elif isinstance(descendant, Tag) and descendant.name == 'img':
            elements.append(str(descendant))
            imgs.append(str(descendant))

    return ''.join(elements), ', '.join(imgs)


def shorten_chapter(chapter, model='gpt-3.5-turbo', ratio=0.1):
    text, imgs = chap2text(chapter.get_content())

    if len(text) < MIN_NUM_CHARS_TO_SUMMARIZE:
        return text
    
    num_words = math.ceil(len(text.split()) * args.ratio / 10) * 10

    messages = []
    if len(imgs) > 0:
        prompt = PROMPT_WITH_IMAGE.format(num_words=num_words, text=text, imgs=imgs)
        messages.append({"role": "system", "content": SYSTEM_PROMPT_WITH_IMAGE})
    else:
        prompt = PROMPT_WITHOUT_IMAGE.format(num_words=num_words, text=text)
    messages.append({"role": "user", "content": prompt})

    completion = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0,
    )

    return completion.choices[0].message.content


def get_toc_from_epub(book):
    toc_items = []
    if book.toc:
        # Recursively parse TOC items
        def parse_node(node):
            if isinstance(node, tuple):
                return {
                    'title': node[0].title,
                    'href': node[0].href,
                    'children': [parse_node(subnode) for subnode in node[1]]
                }
            else:
                return {
                    'title': node.title,
                    'href': node.href,
                }

        toc_items = [parse_node(node) for node in book.toc]

    return toc_items

def remove_unimportant_chapters(toc, book, model='gpt-3.5-turbo'):
    chapters = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            chapters.append(item)

    toc_str = '\n'.join([t.title for t in toc])
    completion = openai.ChatCompletion.create(
        model=model,
        messages=[{"role": "user", "content": TOC_PROMPT.format(toc=toc_str)}],
        temperature=0,
    )

    new_toc_list = completion.choices[0].message.content.split('\n')
    new_toc = []
    for t in toc:
        if t.title in new_toc_list:
            new_toc.append(t)
    
    shortened_toc_chapters = [t.href for t in new_toc]
    toc_chapters = [t.href for t in toc]
    shotend_chapters = []
    adding = False
    for chapter in chapters:
        if chapter.get_name() in toc_chapters:
            
            if chapter.get_name() in shortened_toc_chapters:
                shotend_chapters.append(chapter)
                adding = True
            else:
                adding = False
        elif adding:
            shotend_chapters.append(chapter)

    return new_toc, shotend_chapters

if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser(description='Tiny Books: Shorten books with AI')
    parser.add_argument('input', type=str, help='Path to the input file')
    parser.add_argument('--output', type=str, default=None, help='Path to the output file. If not specified, a file with the same name and the suffix "_tiny" will be created.')
    parser.add_argument('--openai-key', type=str, default=None, help='OpenAI API key. If not specified, the key will be read from the environment variable OPENAI_KEY.')
    parser.add_argument('--openai-org', type=str, default=None, help='OpenAI organization ID. If not specified, the key will be read from the environment variable OPENAI_ORG.')
    parser.add_argument('--openai-model', type=str, default='gpt-3.5-turbo', help='Which OpenAI model to use.')
    parser.add_argument('--ratio', type=float, default=0.15, help='Length ratio of the shortend version to the original version.')
    args = parser.parse_args()

    if args.openai_key is not None:
        openai.api_key = args.openai_key
    if args.openai_org is not None:
        openai.organization = args.openai_org

    if args.output is None:
        args.output = str(Path(args.input).stem + '_tiny' + Path(args.input).suffix)

    # Read epub
    book = epub.read_epub(args.input)

    # Remove unimportant chapters from table of contents
    old_important_toc, old_important_chapters = remove_unimportant_chapters(book.toc, book)
    
    # Shorten each chapter
    shortend_chapters = [
        shorten_chapter(chapter, model=args.openai_model, ratio=args.ratio) 
        for chapter in tqdm(old_important_chapters)
    ]

    # Create new book
    new_book = epub.EpubBook()
    # new_book.set_title(book.get_metadata('DC', 'title'))
    # new_book.add_author(book.get_metadata('DC', 'creator'))
    
    # Add chapters
    for i in range(len(old_important_chapters)):
        c = epub.EpubHtml(file_name=old_important_chapters[i].get_name())
        c.content = f'<html><p>' + "</p><p>".join(shortend_chapters[i].split("\n")) + '</p></html>'
        new_book.add_item(c)

    # add images
    for image in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        new_book.add_item(image)
    
    # Add table of contents
    # TODO
    # new_book.toc = important_toc
    
    # save to file
    epub.write_epub(args.output, new_book)
