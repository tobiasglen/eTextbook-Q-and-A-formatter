import os
import random
import re
import argparse
import unicodedata
from rich.table import Table
from rich.panel import Panel
from bs4 import BeautifulSoup
from rich.prompt import Prompt, Confirm
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
    console.clear()
    console.print(f'\nYou selected: [green bold]{temp_selection_store[selection]}[/green bold]\n')
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
    console.clear()
    console.print(f'\nYou selected: [green bold]{temp_selection_store[selection]}[/green bold]\n')
    return part_chapters[temp_selection_store[selection]], temp_selection_store[selection]


user_part_selection = select_part()
user_chapter_selection = select_chapter(user_part_selection)

# We'll use this to store the chapter's questions/answers/options/explanation
question_answer_store = {}

# Now we open the book up again & find the chapter the user selected
for item in book.get_items_of_type(ITEM_DOCUMENT):
    if item.file_name == user_chapter_selection[0]:
        console.print(f'\n[green][bold]Success![/bold] We found the following chapter:[/green][deep_sky_blue1]{user_chapter_selection[1]}[/deep_sky_blue1]\n', highlight=False)
        # console.print(item.get_content())
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        # console.print(soup.prettify())

        # Find the questions and answers
        for question_or_answer in soup.find_all('p', class_=['ques', 'ques1']):

            # This is the ID of the question or answer, they are slightly different which is why we have a standardized ID we define below (remove unique prefix)
            q_or_a_id = question_or_answer.find('a', href=True)['id']

            # Set a key we can use to store the question and answer
            qa_key = str(q_or_a_id).removeprefix('r_')
            # Identify if this is a question or answer by check the link id
            if q_or_a_id.startswith('r_'):  # This is a question
                # Set the question value now and also the choices for the question. We can't set the answer yet because its only revealed later in the chapter (need more loops)
                clean_question = unicodedata.normalize("NFKD", question_or_answer.text)

                question_answer_store[qa_key] = {'question': unicodedata.normalize("NFKD", clean_question[3:].strip()), 'answer': [], 'explanation': '', 'choices': {}}
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
                question_answer_store[qa_key]['answer'] = answer_re_match.group(2).replace('and', '').replace(' ', '').split(',')
                question_answer_store[qa_key]['explanation'] = answer_re_match.group(3).lstrip()
        # If we've found the correct chapter & finished collecting the questions and answers, break out of the loop
        break



# Randomize the order of the questions & start the quiz
quiz_key_order = list(question_answer_store.keys())
random.shuffle(quiz_key_order)

# Keep track of the user's score and if a user gets a question wrong but tries again do not count it as a correct answer
user_results = {}


for q_index, question_key in enumerate(quiz_key_order):
    user_results[question_key] = {'points': -1, 'guess': []}
    while True:
        console.clear()
        console.print(Panel(f'Quiz | {user_chapter_selection[1]} | Question {q_index + 1}/{len(quiz_key_order)}', style='bold green'))

        console.print(f'\n{question_answer_store[question_key]["question"]}\n', style='chartreuse3 bold')
        # Print the choices
        for choice_key, choice in question_answer_store[question_key]['choices'].items():
            console.print(f'[green bold]{choice_key}.[/green bold] [sky_blue3]{choice}[/sky_blue3]')

        # Get the user's answer
        if len(question_answer_store[question_key]['answer']) > 1:  # First we need to check if this is a "Choose all that apply" question
            # Remove all whitespace, leading and trailing commas and split the answer into a list using commas as the delimiter
            user_answer = console.input(f'\n[medium_purple3]Your Answer (comma separated):[/medium_purple3]').replace(' ', '').strip(',').split(',')
        else:
            # Even if this is a single answer question, we still store it as a list so, we can use the same code for multiple answers (list comparison) (Also, we already store the correct answer as a list :shrug:)
            user_answer = Prompt.ask(f'\n[medium_purple3]Your Answer:[/medium_purple3]', choices=[*question_answer_store[question_key]['choices']]).split()

        # Check if the user got the question right (Single/Multiple answers are stored as lists for code re-usability)
        if set(user_answer) == set(question_answer_store[question_key]['answer']):
            # Check if this is the users first attempt at this question & if so, give them a point
            if user_results[question_key]['points'] == -1:
                user_results[question_key]['points'] = 1
            console.line()
            console.rule('[chartreuse3 bold]Correct![/chartreuse3 bold]')
            console.print(f'[sky_blue3]{question_answer_store[question_key]["explanation"]}[/sky_blue3]')
            if Confirm.ask(f'\n[green bold]Continue?[/green bold]', default=True):
                break

        else:
            # Check if this is the users first attempt at this question & if so, give them zero points
            if user_results[question_key]['points'] == -1:
                user_results[question_key]['points'] = 0

            # If the user got the question wrong, append the user's attempt to the list of guesses
            user_results[question_key]['guess'].append(user_answer[0])
            console.line()
            console.rule(title='[red]Incorrect![/red]', style='red')
            if Confirm.ask('\n[yellow3 bold]Try Again?[/yellow3 bold]', default=True):
                continue
            else:
                user_results[question_key]['points'] = 0
                break

# Print the user's results
console.clear()
console.print(Panel(f'Quiz | {user_chapter_selection[1]} | Results', style='bold green'))

total_points = 0

console.print(f'\n[green bold]Incorrect Answers:[/green bold]')
for question_key, question_result in user_results.items():
    total_points += question_result['points']
    if question_result['points'] == 0:
        console.print(question_answer_store[question_key]["question"], style='bold')

        # Print the choices & color the user's answer(s) red
        for choice_key, choice in question_answer_store[question_key]['choices'].items():
            if choice_key in question_result['guess']:
                console.print(f'[bold]{choice_key}[/bold]. {choice} [medium_purple4](Your guess)[/medium_purple4]', style='red')

            elif choice_key in question_answer_store[question_key]['answer']:
                console.print(f'[bold]{choice_key}[/bold]. {choice}', style='dark_olive_green2')

            else:
                console.print(f'[bold]{choice_key}[/bold]. {choice}', style='steel_blue')

        console.print(question_answer_store[question_key]["explanation"], style='sky_blue3')

        console.rule()














