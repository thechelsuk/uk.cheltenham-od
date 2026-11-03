# frozen_string_literal: true

# Kramdown writes a right-aligned Markdown table column (`--:`) as
# style="text-align: right" on every cell. The site doesn't use inline styles
# (see the style guide), so after a page is rendered this swaps it for the
# site's `number` class, which right-aligns the same way. Left is the default
# alignment, so a left-aligned column (`:--`) just loses its style.
module TableAlignment
  ALIGNED_CELL = /<(td|th) style="text-align: (right|left)">/

  def self.clean(doc)
    return unless doc.output&.include?('style="text-align: ')

    doc.output = doc.output.gsub(ALIGNED_CELL) do
      cell = Regexp.last_match(1)
      Regexp.last_match(2) == "right" ? %(<#{cell} class="number">) : "<#{cell}>"
    end
  end
end

Jekyll::Hooks.register [:pages, :documents], :post_render do |doc|
  TableAlignment.clean(doc)
end
