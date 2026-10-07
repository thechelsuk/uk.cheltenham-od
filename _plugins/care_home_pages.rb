# frozen_string_literal: true

# One page per care home and home care service, generated from _data/cqc.json.
#
# The monthly fetcher (_python/cqc.py) gives every care home and home care
# service a slug; each gets a page at /cheltenham-care-homes/<slug>, rendered
# by _layouts/care-home.html. A newly registered service gets its page on the
# next build without anyone writing a front-matter file for it.

module CareHomePages
  SEO_LIMIT = 160
  TITLE_LIMIT = 60
  KINDS = {
    "nursing_home" => "nursing home",
    "residential_home" => "residential care home",
    "home_care" => "home care service",
  }.freeze

  module_function

  def place(location)
    town = location["address"].to_s.split(", ").last.to_s
    return location["name"] if town.empty? || location["name"].downcase.include?(town.downcase)

    "#{location['name']}, #{town}"
  end

  # The search-result title: the fullest version that fits within TITLE_LIMIT, so short names still get a
  # descriptive title and long ones don't run over. "Name - Detail" names fall back to just the name.
  TITLE_KINDS = {
    "nursing_home" => "Nursing Home",
    "residential_home" => "Care Home",
    "home_care" => "Home Care",
  }.freeze

  def seo_title(location)
    name = location["name"]
    short = name.split(" - ").first
    kind = TITLE_KINDS[location["kind"]]
    [
      "#{name}: #{kind} CQC Rating, Cheltenham",
      "#{name}: CQC Rating, Cheltenham",
      "#{name} CQC Rating",
      "#{short}: CQC Rating, Cheltenham",
      "#{short} CQC Rating",
    ].find { |text| text.length <= TITLE_LIMIT } || short
  end

  def seo(location)
    name = location["name"]
    kind = KINDS[location["kind"]]
    [
      "#{name}, a #{kind} in #{location['postcode']}: its latest CQC rating, how it scored on safety, care and leadership, and the care it offers.",
      "#{name}: latest CQC rating, scores on safety, care and leadership, and the care it offers.",
      "#{name}: latest CQC rating and the care it offers.",
    ].find { |text| text.length <= SEO_LIMIT } || "#{name}: CQC rating."
  end

  class Generator < Jekyll::Generator
    safe true
    priority :normal

    def generate(site)
      (site.data.dig("cqc", "locations") || []).each do |location|
        next unless location["slug"]

        page = Jekyll::PageWithoutAFile.new(site, site.source, "cheltenham-care-homes", "#{location['slug']}.html")
        page.data.merge!(
          "layout" => "care-home",
          "cqc_id" => location["id"],
          "title" => "#{location['name']}: CQC Rating and Care",
          "seo_title" => CareHomePages.seo_title(location),
          "seo" => CareHomePages.seo(location),
          "description" => "The latest Care Quality Commission rating and the care offered by #{CareHomePages.place(location)}, " \
                           "a #{CareHomePages::KINDS[location['kind']]} in Cheltenham.",
          "permalink" => "/cheltenham-care-homes/#{location['slug']}",
          "type" => "community",
          "schema" => "care-home"
        )
        site.pages << page
      end
    end
  end
end
