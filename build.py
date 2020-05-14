#!/usr/bin/env python3

# Imports and global variables {{{

import os
import re
import shutil
import subprocess
import sys
import json


VWDIR = '/home/oscar/Documents/wiki'
F_JSON_TOC = os.path.join(VWDIR, 'build', 'toc.json')
F_JSON_CATEGORIES = os.path.join(VWDIR, 'build', 'categories.json')
F_MD_TOC = os.path.join(VWDIR, 'toc.md')
data = {}

# /Imports and global variables }}}

# Generate JSON {{{

def file_create_data(file):
    f = {}
    path, ext = os.path.splitext(os.path.relpath(file, VWDIR))
    f['path'] = path
    with open(file, 'r') as f1:
        content = f1.read()

    lines = content.split('\n')
    n = 0

    # Title
    if lines[n][:7] == '%title ' and len(lines[n]) > 7:
        f['title'] = lines[n][7:]
        n += 1
    else:
        f['title'] = path

    # Date
    if lines[n][:6] == '%date ' and len(lines[n]) > 6:
        f['date'] = lines[n][6:]
        n += 1

    # Categories and tags
    f['categories'] = []
    f['tags'] = []
    if len(lines[n]) > 2 and lines[n][0] == ':' and lines[n][-1] == ':':
        tags = lines[n][1:-1].split(':')
        for tag in tags:
            if tag[:2] == 'c-':
                f['categories'].append(tag[2:])
            else:
                f['tags'].append(tag)
        n += 1

    if len(f['categories']) == 0:
        f['categories'].append('uncategorized')

    # Description
    if n == 0 or lines[n] == '':
        if lines[n] == '':
            n += 1
        if len(lines[n]) > 0 and lines[n][0] != '#' and lines[n][0] != '-':
            while lines[n] != '':
                if not 'description' in f:
                    f['description'] = ''
                if f['description'] != '':
                    f['description'] += ' '
                f['description'] += lines[n]
                n += 1

    f['sort_key'] = f['title']

    return f, n


def process_files():
    global data
    for root, dirs, files in os.walk(VWDIR):
        dirs[:] = [d for d in dirs if d not in ['build']]
        for f in files:
            if f[-3:] == '.md' and os.path.join(VWDIR, root, f) != F_MD_TOC:
                f_data = file_create_data(os.path.join(VWDIR, root, f))[0]
                data['files'].append(f_data)



def process_categories():
    global data
    for file in data['files']:
        for cat in file['categories']:
            if not cat in data['categories']:
                data['categories'][cat] = {
                    'name': cat,
                    'sort_key': cat,
                    'files': []
                }
            if not 'files' in data['categories'][cat]:
                data['categories'][cat]['files'] = []

            data['categories'][cat]['files'].append(file)

# /Generate JSON }}}

# Generate MD {{{

def file_to_markdown(f):
    date = ' (' + f['date'] + ')' if 'date' in f else ''
    des = ': ' + f['description'] if 'description' in f else ''
    return '[' + f['title'] + '](' + f['path'] + ')' + date + des


def generate_md_toc():
    s = '%title Table of Contents\n'
    for k, cat in sorted(data['categories'].items(), key=lambda x : x[1]['sort_key']):
        if 'files' in cat and k != 'notoc':
            s += '\n'
            if k != 'root':
                s += '## ' + cat['name'] + '\n\n'
            for file in sorted(cat['files'], key=lambda x : x['sort_key']):
                s += '- ' + file_to_markdown(file) + '\n'

    return s

# /Generate MD }}}

# Generate HTML from MD {{{

def dir_to_frontmatter(d, i_file):
    return []


def convert(force, syntax, extension, output_dir, input_file, css_file,
        template_path, template_default, template_ext, root_path, custom_args):

    if shutil.which('pandoc') is None:
        print('Error: pandoc not found', file=sys.stderr)
        sys.exit(1)

    if syntax != 'markdown':
        print('Error: Unsupported syntax', file=sys.stderr)
        sys.exit(1)

    input_file_name = os.path.splitext(os.path.basename(input_file))[0]
    output_file = os.path.join(output_dir, input_file_name) + os.path.extsep + 'html'

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.read()

    rel_input_file = os.path.relpath(input_file, VWDIR)

    # Format links for HTML
    lines = re.sub('\[([^]]+)\]\(([^)#]*)(?:#([^)]*))?\)', repl, lines)

    # Create metadata
    frontmatter_dict, n = file_create_data(input_file)
    frontmatter_dict['ltoc'] = []

    frontmatter = '---\n' + json.dumps(frontmatter_dict) + '\n---\n'
    lines = frontmatter + lines.split('\n', n)[n]

    # root_path doesn't give a path if on root folder already
    root_rel = os.path.relpath(VWDIR, os.path.dirname(input_file))

    template = os.path.join(template_path, template_default + os.path.extsep + template_ext)
    command = [
        'pandoc',
        '--section-divs',
        '--template=build/template.html',
        '--toc',
        '--css',
        os.path.join(root_rel, 'style.css'),
        '--variable',
        'relpath=' + root_rel,
        '-s',
        '--highlight-style=pygments',
        #'--metadata',
        #'pagetitle={}'.format(title),
        custom_args if custom_args != '-' else '',
        '-f',
        'markdown',
        '-t',
        'html5',
        '-o',
        output_file,
        '-',
    ]

    # Prune empty elements from command list
    command = list(filter(None, command))

    # Run command
    subprocess.run(command, check=True, encoding='utf8', input=lines)


def repl(match):
    link = match.group(2)
    if not re.search('://', match.group(2)):
        link += '.html'
        if match.group(3):
            link += '#' + match.group(3).replace(' ', '-').lower()
    return "[{}]({})".format(match.group(1), link)

# /Generate HTML from MD }}}

# Main {{{

def make_toc():
    global data
    with open(F_JSON_CATEGORIES, 'r') as f:
        s = f.read()
    data['categories'] = json.loads(s)
    data['files'] = []

    # Generate data
    process_files()
    process_categories()

    # Save data to JSON
    with open(F_JSON_TOC, 'w') as f:
        json.dump(data, f)

    # Generate wiki TOC
    s = generate_md_toc()
    with open(F_MD_TOC, 'w') as f:
        f.write(s)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        make_toc()
    else:
        with open(os.path.join(VWDIR, 'out.txt'), "a") as f:
            f.write(' '.join(sys.argv) + '\n')
        if sys.argv[5] == os.path.join(VWDIR, 'index.md'):
            make_toc()
            shutil.copyfile(os.path.join(VWDIR, 'build', 'style.css'),
                    os.path.join(VWDIR, 'build', 'html', 'style.css'))
        with open(F_JSON_TOC, 'r') as f:
            s = f.read()
        data = json.loads(s)

        convert(*sys.argv[1:])

# /Main }}}
