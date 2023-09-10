import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, NavigableString, Tag


def chap2text(chap):
    soup = BeautifulSoup(chap, 'html.parser')

    elements = []
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

    return ''.join(elements)


def shorten_chapter(chapter):
    text = chap2text(chapter.get_content())
    return text


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

def shorten_toc(toc, book):
    chapters = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            chapters.append(item)
    
    shortened_toc = toc[3:4] # TODO
    shortened_toc_chapters = [t['href'] for t in shortened_toc]
    toc_chapters = [t['href'] for t in toc]
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

    return shortened_toc, shotend_chapters

if __name__ == "__main__":
    input_epub = 'book.epub'
    output_epub = 'shortened_book.epub'
    book = book = epub.read_epub(input_epub)
    toc = get_toc_from_epub(book)
    toc, chapters = shorten_toc(toc, book)
    shortend_chapters = [shorten_chapter(chapter) for chapter in chapters]

    # Create new book
    new_book = epub.EpubBook()
    # new_book.set_title(book.get_metadata('DC', 'title'))
    # new_book.add_author(book.get_metadata('DC', 'creator'))
    
    # Add chapters
    for i in range(len(chapters)):
        c = epub.EpubHtml(file_name=chapters[i].get_name())
        c.content = f'<html><p>' + "</p><p>".join(shortend_chapters[i].split("\n")) + '</p></html>'
        new_book.add_item(c)

    # add images
    for image in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        new_book.add_item(image)
    
    # Add table of contents
    # new_book.toc = toc
    
    # save to file
    epub.write_epub(output_epub, new_book)
