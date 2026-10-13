"""A deliberately small TeX presentation reader, never a TeX interpreter.

Only the trusted templates' presentation commands are recognized. Escaped values
become text nodes. Output is an AST, not HTML; unsupported syntax remains text.
"""
import re

def node(kind, children=None, **values):
    return {'kind': kind, **values, **({'children': children} if children is not None else {})}

class Reader:
    def __init__(self, source):
        self.source = source
        self.i = 0

    def group(self):
        while self.i < len(self.source) and self.source[self.i].isspace():
            self.i += 1
        if self.i >= len(self.source) or self.source[self.i] != '{':
            return []
        self.i += 1
        return self.read('}')

    def read(self, stop=None):
        out = []
        while self.i < len(self.source):
            if stop and self.source.startswith(stop, self.i):
                self.i += len(stop)
                break
            char = self.source[self.i]
            if char == '{':
                out.extend(self.group())
            elif char == '\\':
                self.i += 1
                match = re.match(r'[A-Za-z]+\*?|.', self.source[self.i:], re.S)
                if not match:
                    break
                command = match.group()
                self.i += len(command)
                if command in ('textbackslash', 'textasciitilde', 'textasciicircum'):
                    self.group()
                    out.append(node('text', text={'textbackslash':'\\','textasciitilde':'~','textasciicircum':'^'}[command]))
                elif command in '#$%&_{} ':
                    out.append(node('text', text=command))
                elif command in ('textbf','underline','emph','textit'):
                    kind = 'strong' if command == 'textbf' else 'underline' if command == 'underline' else 'emphasis'
                    out.append(node(kind, self.group()))
                elif command in ('section*','subsection*','heading','assessment'):
                    out.append(node('heading',self.group(),level=2 if command=='section*' else 3))
                elif command == 'field':
                    title = self.group()
                    contents = self.group()
                    out.append(node('group',[node('strong',title),node('text',text=': '),*contents]))
                elif command in ('par','newline','\\'):
                    out.append(node('break'))
                elif command in ('bigskip','medskip','smallskip','large','Large','normalsize'):
                    pass
                elif command == 'newpage':
                    out.append(node('pagebreak'))
                elif command == 'rule':
                    self.group(); self.group()
                    out.append(node('rule'))
                elif command == 'item':
                    out.append(node('item-marker'))
                elif command == 'begin':
                    env = ''.join(n.get('text','') for n in self.group())
                    if env == 'tabular':
                        self.group()  # column alignment, not content
                        contents = self.read(r'\end{tabular}')
                        rows, cells, current = [], [], []
                        for part in contents + [node('break')]:
                            if part['kind'] in ('cell-marker','break'):
                                cells.append(node('cell',current)); current=[]
                                if part['kind']=='break':
                                    if any(any(p['kind'] != 'text' or p['text'].strip() for p in c['children']) for c in cells):
                                        rows.append(node('row',cells))
                                    cells=[]
                            else:
                                current.append(part)
                        out.append(node('table',rows))
                    else:
                        contents = self.read('\\end{' + env + '}')
                        if env in ('itemize','enumerate'):
                            items=[]
                            for part in contents:
                                if part['kind']=='item-marker': items.append(node('item',[]))
                                elif items: items[-1]['children'].append(part)
                            out.append(node('list',items,ordered=env=='enumerate'))
                        else:
                            out.append(node('center' if env=='center' else 'group',contents))
                else:
                    out.append(node('text', text='\\'+command))
            elif char == '&':
                self.i += 1
                out.append(node('cell-marker'))
            else:
                start = self.i
                while self.i < len(self.source) and self.source[self.i] not in '\\{&' and not (stop and self.source.startswith(stop,self.i)):
                    self.i += 1
                text = self.source[start:self.i]
                # TeX ordinary whitespace collapses; blank lines separate paragraphs.
                for index, paragraph in enumerate(re.split(r'\n\s*\n',text)):
                    if index: out.append(node('break'))
                    clean = re.sub(r'\s+',' ',paragraph)
                    if clean: out.append(node('text', text=clean))
        return out

def draft_preview(latex: str):
    body = latex.split(r'\begin{document}',1)[1].rsplit(r'\end{document}',1)[0]
    return {'blocks': Reader(body).read(), 'label': 'Draft Preview'}
