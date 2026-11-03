# frozen_string_literal: true

# Markdown tables come out of Kramdown as a bare <table>, without the classes
# the HTML layouts write by hand. After a page is rendered this gives them the
# same treatment:
#
# - the table is wrapped in <div class="table-scroll"> so it scrolls sideways
#   on a phone, and gets the `data-table` class;
# - a right-aligned column (`--:`), which Kramdown writes as
#   style="text-align: right" on every cell, gets the `number` class instead
#   (the site doesn't use inline styles); a left-aligned one just loses its
#   style, as left is the default;
# - a cell that is wholly a UK postcode gets the `postcode` class, and one that
#   is wholly a date (YYYY-MM-DD, or YYYY-MM-DD HH:MM) gets `date`, so neither
#   wraps.
module TableAlignment
  ALIGNED_CELL = /<(td|th) style="text-align: (right|left)">/
  BARE_TABLE = %r{<table>(.*?)</table>}m
  POSTCODE_CELL = %r{<td>(\s*[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}\s*)</td>}
  DATE_CELL = %r{<td>(\s*\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?\s*)</td>}

  def self.clean(doc)
    return unless doc.output&.include?("<table>") || doc.output&.include?('style="text-align: ')

    html = doc.output.gsub(ALIGNED_CELL) do
      cell = Regexp.last_match(1)
      Regexp.last_match(2) == "right" ? %(<#{cell} class="number">) : "<#{cell}>"
    end
    doc.output = html.gsub(BARE_TABLE) do
      body = Regexp.last_match(1)
                   .gsub(POSTCODE_CELL) { %(<td class="postcode">#{Regexp.last_match(1)}</td>) }
                   .gsub(DATE_CELL) { %(<td class="date">#{Regexp.last_match(1)}</td>) }
      %(<div class="table-scroll"><table class="data-table">#{body}</table></div>)
    end
  end
end

Jekyll::Hooks.register [:pages, :documents], :post_render do |doc|
  TableAlignment.clean(doc)
end
