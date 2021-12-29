import os
import random
import re
import argparse
import unicodedata

from rich.table import Table
from bs4 import BeautifulSoup
from rich.prompt import Prompt
from rich.pretty import pprint
from rich.console import Console
from ebooklib import epub, ITEM_DOCUMENT

console = Console()

# set up the argument parser
parser = argparse.ArgumentParser(description='Read an EPUB file & print the Chapter Review Q/A')
parser.add_argument('-i', '--input', help='Input EPUB file', required=True)
args = parser.parse_args()

# Verify the input file exists
if not os.path.isfile(args.input):
    console.print(f'[red][bold]Error![/bold] The file below does not exist.[/red]\n{args.input}\n', highlight=False)
    exit()


# Load the EPUB file with ebooklib
book = epub.read_epub(args.input)

# Let the user know we opened the file & print the title
console.clear()
console.print(f'[green][bold]Success![/bold] We found the following book:[/green]\n[deep_sky_blue1]{book.title}[/deep_sky_blue1]\n', highlight=False)


contents = []
for item in book.get_items_of_type(ITEM_DOCUMENT):
    contents.append(item.get_content())

# In our book, we have a "Contents at a Glance" section which has links to the Parts & Chapters of the book
book_index = contents[0]

# This dictionary will hold the Part as the key and a nested dictionary of chapter names/links as the value
pt_name__ch_index = {}


soup = BeautifulSoup(book_index, 'html.parser')
current_part = ''  # This will hold the current part name
# Find a href tags and print the text
for link in soup.find_all('a'):
    # find all matches that use the format: <a href="part1.xhtml#part1">Part I Threats, Attacks, and Vulnerabilities</a>
    match = re.search(r'<a href="(.*)#(.*)">(.*)</a>', str(link))
    if match:

        part_name = match.group(3)  # This currently can be a Part or Chapter. In the next line we will check for "Part" and only add it to the dictionary if it is a Part
        # Check if the word "Part" is in the part name and if it's followed by a roman numeral
        if part_name.startswith("Part") and re.search(r'[IVXLCDM]+', part_name):
            current_part = part_name
            pt_name__ch_index[part_name] = {}

        # Verify the part_name starts with "Chapter" and that it is followed by a single or double digit number
        elif part_name.startswith("Chapter") and re.search(r'[1-9][0-9]?', part_name):  # If the part name is a Chapter, add it to the nested dictionary using the "current_part" variable as the key
            pt_name__ch_index[current_part][part_name] = match.group(1)


# Delete any parts that have no chapters
for part in list(pt_name__ch_index):
    if not pt_name__ch_index[part]:
        del pt_name__ch_index[part]


def select_part():
    # Use rich.table to print the Part names
    table = Table(title="Select a Part", title_style="bold")
    table.add_column("Key", style="cyan")
    table.add_column("Title", style="magenta")
    temp_selection_store = {}
    for index, part in enumerate(list(pt_name__ch_index.keys())):
        table.add_row(str(index + 1), part)
        temp_selection_store[str(index + 1)] = part

    console.print(table)

    # Get the user's selection
    selection = Prompt.ask("Select a Part: ", choices=[*temp_selection_store])
    console.print(f'\nYou selected: [green]{temp_selection_store[selection]}[/green]')
    return pt_name__ch_index[temp_selection_store[selection]]


def select_chapter(part_chapters):
    # Use rich.table to print the Chapter names
    table = Table(title="Select a Chapter", title_style="bold")
    table.add_column("Key", style="cyan")
    table.add_column("Title", style="magenta")
    temp_selection_store = {}
    for index, chapter in enumerate(list(part_chapters.keys())):
        table.add_row(str(index + 1), chapter)
        temp_selection_store[str(index + 1)] = chapter

    console.print(table)

    # Get the user's selection
    selection = Prompt.ask("Select a Chapter: ", choices=[*temp_selection_store])
    console.print(f'\nYou selected: [green]{temp_selection_store[selection]}[/green]')
    return part_chapters[temp_selection_store[selection]]


user_part_selection = select_part()
user_chapter_selection = select_chapter(user_part_selection)

# We'll use this to store the chapter's questions/answers/options/explanation
question_answer_store = {}

# Now we open the book up again & find the chapter the user selected
for item in book.get_items_of_type(ITEM_DOCUMENT):
    if item.file_name == user_chapter_selection:
        console.print(f'\n[green][bold]Success![/bold] We found the following chapter:[/green]\n[deep_sky_blue1]{item.title}[/deep_sky_blue1]\n', highlight=False)
        # console.print(item.get_content())
        soup = BeautifulSoup(item.get_content(), 'html.parser')

        # Find the questions and answers
        for question_or_answer in soup.find_all('p', class_='ques'):

            # This is the ID of the question or answer, they are slightly different which is why we have a standardized ID we define below (remove unique prefix)
            q_or_a_id = question_or_answer.find('a', href=True)['id']

            # Set a key we can use to store the question and answer
            qa_key = str(q_or_a_id).removeprefix('r_')

            # Identify if this is a question or answer by check the link id
            if q_or_a_id.startswith('r_'):  # This is a question
                # Set the question value now and also the choices for the question. We can't set the answer yet because its only revealed later in the chapter (need more loops)
                clean_question = unicodedata.normalize("NFKD", question_or_answer.text)

                question_answer_store[qa_key] = {'question': unicodedata.normalize("NFKD", clean_question[2:].strip()), 'answer': [], 'explanation': '', 'choices': {}}
                # Add the multiple choice options
                for option in question_or_answer.find_next_siblings('p', class_='alpha', limit=4):
                    question_answer_store[qa_key]['choices'].update({option.text[:1]: unicodedata.normalize("NFKD", option.text[2:].strip())})

            else:  # This is an answer
                # The only thing left to do is to set the answer for the question
                clean_answer = unicodedata.normalize("NFKD", question_or_answer.text)

                answer_re_match = re.match(r'(\d+)\.(.*[A-Z])\.(.*)', clean_answer)
                if not answer_re_match:
                    console.print(f'\n[red]Error[/red] - The answer [yellow]{clean_answer}[/yellow] does not match the expected format.\n')
                    continue
                question_answer_store[qa_key]['answer'] = answer_re_match.group(2).replace('and', ',').replace(' ', '').split(',')
                question_answer_store[qa_key]['explanation'] = answer_re_match.group(3).lstrip()

        # If we've found the correct chapter & finished collecting the questions and answers, break out of the loop
        break


# pprint(question_answer_store, expand_all=True)


# Now we'll use the question_answer_store to create the quiz
# Use a while loop to keep asking questions until the user answers all of them correctly or quits
while True:
    random_question = random.choice(list(question_answer_store.keys()))
    choices = question_answer_store[random_question]['choices']
    answer = question_answer_store[random_question]['answer']
    explanation = question_answer_store[random_question]['explanation']
    console.clear()
    console.print(f'\n[green]{question_answer_store[random_question]["question"]}[/green]\n')
    for choice in choices:
        console.print(f'[green]{choice}[/green] - {choices[choice]}')
    user_guess_input = Prompt.ask('Input:', choices=list(choices.keys()))
    if user_guess_input in answer:
        console.print(f'\n[green]Correct![/green]\n')
    else:
        console.print(f'\n[red]Incorrect![/red]\n')
        console.print(f'[green]The correct answer is:[/green]\n')
        for answer_choice in answer:
            console.print(f'[green]{answer_choice}[/green] - {choices[answer_choice]}')
        console.print(f'\n[green]{explanation}[/green]\n')
    user_continue_input = Prompt.ask('Continue?', choices=['y', 'n'])
    if user_continue_input == 'n':
        break














