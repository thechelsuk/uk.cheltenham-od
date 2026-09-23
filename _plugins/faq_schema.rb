# frozen_string_literal: true

# FAQ structured data, generated from the FAQs a visitor actually sees.
#
# Wrap a page's FAQ section in <section class="faqs"> (or, in Markdown,
# <section class="faqs" markdown="1">). The first heading inside is the
# section title, headings at the next level down are the questions, and
# everything up to the following question is the answer. After the page is
# rendered, this adds a matching FAQPage JSON-LD block to its <head>, so the
# structured data can never drift from the page text. It works for Liquid
# values in templated FAQs (the ward pages) because it reads the final HTML.
#
# It also sets page.has_faqs before rendering, for the admin page's checks.

require "json"
require "kramdown"

module FaqSchema
  SECTION = %r{<section\b[^>]*\bclass="[^"]*\bfaqs\b[^"]*"[^>]*>(.*?)</section>}m.freeze
  HEADING = %r{<h([2-6])\b[^>]*>(.*?)</h\1>}m.freeze
  MARKER = /class="[^"]*\bfaqs\b/.freeze

  module_function

  def text(html)
    # Block tags become spaces; inline ones (links, emphasis) just go.
    plain = html.gsub(%r{</?(p|li|ul|ol|br|div|h[1-6]|tr|td|th)\b[^>]*>}i, " ").gsub(/<[^>]+>/, "")
    plain = plain.gsub(/&(#x?[0-9a-f]+|[a-z][a-z0-9]*);/i) do
      ref = Regexp.last_match(1)
      if ref.start_with?("#x", "#X") then [ref[2..].to_i(16)].pack("U")
      elsif ref.start_with?("#") then [ref[1..].to_i].pack("U")
      else named_entity(ref)
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

  # [[question, answer], ...] from the inner HTML of one faqs section.
  def pairs(section)
    headings = section.to_enum(:scan, HEADING).map { Regexp.last_match }
    return [] if headings.length < 2

    level = headings[1][1]
    questions = headings.drop(1).select { |m| m[1] == level }
    questions.map do |q|
      stop = headings.find { |m| m.begin(0) > q.begin(0) && m[1] <= level }
      answer = section[q.end(0)...(stop ? stop.begin(0) : section.length)]
      [text(q[2]), text(answer)]
    end.reject { |question, answer| question.empty? || answer.empty? }
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

  def inject(doc)
    return unless doc.output_ext == ".html" && doc.output&.include?("faqs")

    found = doc.output.scan(SECTION).flat_map { |(inner)| pairs(inner) }
    return if found.empty?

    if doc.output.include?('"FAQPage"')
      Jekyll.logger.warn "FAQ schema:", "#{doc.relative_path} already has FAQPage JSON-LD; skipped"
      return
    end
    doc.output = doc.output.sub("</head>") { "#{json_ld(found)}</head>" }
  end

  # True when the page's own content or any layout it renders through has a
  # faqs section.
  def faqs?(doc, site)
    return true if doc.content.to_s.match?(MARKER)

    name = doc.data["layout"]
    seen = []
    while name && !seen.include?(name) && (layout = site.layouts[name])
      return true if layout.content.match?(MARKER)

      seen << name
      name = layout.data["layout"]
    end
    false
  end
end

Jekyll::Hooks.register :site, :pre_render do |site|
  (site.pages + site.documents).each do |doc|
    doc.data["has_faqs"] = FaqSchema.faqs?(doc, site)
  end
end

Jekyll::Hooks.register [:pages, :documents], :post_render do |doc|
  FaqSchema.inject(doc)
end
