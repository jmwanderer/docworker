"""
Utility to extract text information from DOCX (MS WORD) files.
Resulting text is intended to be useful for GPT language models.
"""

import docx
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
import io

class DocXExtract:
    def __init__(self, structured=False):
        self.result = io.StringIO()
        self.structured = structured

    def load_doc(self, file):
        """
        Load and parse docx content from a file.
        Note: file should be open as 'rb'
        """
        doc = docx.Document(file)
        self.process_block(doc)
        self.result.seek(0)

    def get_result(self):
        return self.result
 
    def process_block(self, block):
        # Iterate over children of block items
        for item in self.iter_block_items(block):
            if isinstance(item, Table):
                self.format_table(item)
            elif isinstance(item, Paragraph):
                if len(item.text.strip()) == 0:
                    continue
                if (item._p.style is not None):
                    if ((item._p.style.startswith('Heading') or
                        item._p.style.startswith('Title')) and 
                        self.structured):
                        print('<%s>' % item._p.style, file=self.result)
                print(item.text, file=self.result)
            print(file=self.result)


    def iter_block_items(self, parent):
        """
        Yield each paragraph and table child within *parent*, in document order.
        Each returned value is an instance of either Table or Paragraph.
        """
        if isinstance(parent, Document):
            parent_elm = parent.element.body
        elif isinstance(parent, _Cell):
            parent_elm = parent._tc
        else:
            raise ValueError("something's not right")

        for child in parent_elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)

    def dump_table(self, table):
        """
        Generate table contents as a smiple grid
        """
        if self.stuctured:
            print('<table>', file=self.result)    
        for row in table.rows:
            items = []
            for c in row.cells:
                items.append(self.strip_text(c.text))
            print(' | '.join(items), file=self.result)
        if self.stuctured:
            print('</table>', file=self.result)        

    def strip_text(self, text):
        # combine multiple lines into one
        return text.replace('\n', ' ').replace('  ', ' ')
        
    def format_table(self, table):
        """
        Extract information from a table.
        Large tables are converted to records that include
        what is assumed to be row and column headers.
        """
        # Handle multi-cell spans, don't report same combination twice.
        reported_tuples = {}

        row_count, col_count = len(table.rows), len(table.columns)
        # Handle a 1x1 table as text.
        if row_count == 1 and col_count == 1:
            self.process_block(table.cell(0, 0))
            return

        # Handle narrow tables as simple grids.
        # TODO: consider looking at the size of the cell contents
        if col_count < 3:
            self.dump_table(table)
            return

        # Reformat table cells into records
        if self.stuctured:
            print('<table>', file=self.result)
        for row in range(1, row_count):
            row_label = table.cell(row, 0)
            if self.stuctured:
                print('<row>', file=self.result)
            for col in range(0, col_count):
                cell_label = table.cell(0, col)
                cell_contents = table.cell(row, col)
                if len(self.strip_text(cell_contents.text)) == 0:
                    continue
                report = (row_label._tc, cell_label._tc, cell_contents._tc)
                if report not in  reported_tuples.keys():
                    reported_tuples[report] = True
                    print('%s: %s' % (self.strip_text(cell_label.text),
                                      self.strip_text(cell_contents.text)),
                          file=self.result)
        if self.stuctured:
            print('</table>', file=self.result) 


def run_tests():
    file_name = 'DRAFT SCAP Key Actions and Work Plan (February 2023).docx'
    file = open(file_name, 'rb')
    docx_extract = DocXExtract()
    docx_extract.load_doc(file)
    print(docx_extract.get_result().read())
    
if __name__ == "__main__":
  run_tests()


