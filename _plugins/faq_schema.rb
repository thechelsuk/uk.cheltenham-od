# frozen_string_literal: true

# FAQ structured data, generated from the FAQs a visitor actually sees.
#
# Every page writes its FAQs the same way: an <h2> reading "Frequently Asked
# Questions", then each question as an <h3> followed by its answer as a <ul>
# (one <li> per point). In Markdown that is "## Frequently Asked Questions",
# "### Question?" and "- answer". After a page is rendered, this reads those
# question and answer pairs and adds a matching FAQPage JSON-LD block to its
# <head>, so the structured data can never drift from the page text. It reads
# the final HTML, so FAQs that use Liquid values (the ward pages) work too.

require "json"
require "kramdown"

module FaqSchema
  HEADING = %r{<h2\b[^>]*>\s*Frequently Asked Questions\s*</h2>}.freeze
  QUESTION = %r{\G\s*<h3\b[^>]*>(.*?)</h3>\s*}m.freeze
  LIST_TAG = %r{<(/?)ul\b[^>]*>}.freeze

  module_function

  def text(html)
    # Block tags become spaces; inline ones (links, emphasis) just go.
    plain = html.gsub(%r{</?(p|li|ul|ol|br|div|h[1-6]|tr|td|th)\b[^>]*>}i, " ").gsub(/<[^>]+>/, "")
    plain = plain.gsub(/&(#x?[0-9a-f]+|[a-z][a-z0-9]*);/i) do
      ref = Regexp.last_match(1)
      if ref.start_with?("#x", "#X") then [ref[2..].to_i(16)].pack("U")
      elsif ref.start_with?("#") then [ref[1..].to_i].pack("U")
      else
        named_entity(ref)
      end
    end
    plain.gsub(/\s+/, " ").strip
  end

  # Kramdown's entity table covers the named references it writes itself
  # (&rsquo;, &ndash;...); anything it doesn't know is left as written.
  def named_entity(name)
    [Kramdown::Utils::Entities.entity(name).code_point].pack("U")
  rescue Kramdown::Error
    "&#{name};"
  end

  # End index of the <ul> starting at pos, counting nested lists, or nil.
  def list_end(html, pos)
    return nil unless html[pos, 3] == "<ul"

    depth = 0
    while (tag = LIST_TAG.match(html, pos))
      depth += tag[1].empty? ? 1 : -1
      pos = tag.end(0)
      return pos if depth.zero?
    end
    nil
  end

  # [[question, answer], ...] for the <h3> + <ul> pairs that follow pos.
  def pairs(html, pos)
    found = []
    while (question = QUESTION.match(html, pos))
      finish = list_end(html, question.end(0))
      break unless finish

      found << [text(question[1]), text(html[question.end(0)...finish])]
      pos = finish
    end
    found.reject { |q, a| q.empty? || a.empty? }
  end

  def json_ld(pairs)
    data = {
      "@context" => "https://schema.org",
      "@type" => "FAQPage",
      "mainEntity" => pairs.map do |question, answer|
        { "@type" => "Question", "name" => question,
          "acceptedAnswer" => { "@type" => "Answer", "text" => answer } }
      end,
    }
    # "</" would close the script element early.
    json = JSON.pretty_generate(data).gsub("</", "<\\/")
    %(<script type="application/ld+json">\n#{json}\n</script>\n)
  end

  def inject(page)
    html = page.output
    return unless page.output_ext == ".html" && html&.include?("Frequently Asked Questions")

    found = []
    html.scan(HEADING) { found.concat(pairs(html, Regexp.last_match.end(0))) }
    return if found.empty?

    if html.include?('"FAQPage"')
      Jekyll.logger.warn "FAQ schema:", "#{page.relative_path} already has FAQPage JSON-LD; skipped"
      return
    end
    page.output = html.sub("</head>") { "#{json_ld(found)}</head>" }
  end
end

Jekyll::Hooks.register :pages, :post_render do |page|
  FaqSchema.inject(page)
end
