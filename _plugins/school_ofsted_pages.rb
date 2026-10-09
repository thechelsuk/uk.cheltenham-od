# frozen_string_literal: true

# One Ofsted history page per school, generated from _data/ofsted.json.
#
# The monthly fetcher (_python/ofsted.py) decides which schools have Ofsted
# reports; every school in its output gets a page at
# /cheltenham-schools/<slug>, rendered by _layouts/school-ofsted.html. A new
# school, or one Ofsted inspects for the first time, gets its page on the next
# build without anyone writing a front-matter file for it.

module SchoolOfstedPages
  SEO_LIMIT = 160

  module_function

  # "The latest Ofsted rating ... for Swell Church of England Primary School,
  # Cotswold": the school's town from its GIAS address, unless already in the name.
  def place(school, gias)
    town = gias&.dig("address").to_s.split(", ").last.to_s
    return school["name"] if town.empty? || school["name"].downcase.include?(town.downcase)

    "#{school['name']}, #{town}"
  end

  # The search-result title: the fullest version that fits within TITLE_LIMIT, so short names still get a
  # descriptive title and long ones don't run over.
  TITLE_LIMIT = 60

  def seo_title(school)
    name = school["name"]
    [
      "#{name}: Ofsted Rating and Reports, Cheltenham",
      "#{name} Ofsted Rating and Reports",
      "#{name} Ofsted Reports",
      "#{name} Ofsted",
    ].find { |text| text.length <= TITLE_LIMIT } || name
  end

  # The longest description that fits the meta description limit.
  def seo(school)
    name = school["name"]
    year = school["first_year"]
    [
      "#{name} Ofsted rating and inspection history: the latest grades by area and every report since #{year}, with links to each one.",
      "#{name} Ofsted rating and inspection history: latest grades and every report since #{year}.",
      "#{name} Ofsted rating and every inspection report since #{year}.",
    ].find { |text| text.length <= SEO_LIMIT } || "#{name} Ofsted rating and inspection history."
  end

  class Generator < Jekyll::Generator
    safe true
    priority :normal

    def generate(site)
      schools = site.data.dig("ofsted", "schools") || {}
      gias = (site.data["schools"] || []).to_h { |s| [s["name"], s] }

      schools.each do |urn, school|
        page = Jekyll::PageWithoutAFile.new(site, site.source, "cheltenham-schools", "#{school['slug']}.html")
        page.data.merge!(
          "layout" => "school-ofsted",
          "urn" => urn,
          "title" => "#{school['name']} Ofsted Rating and Inspection History",
          "seo_title" => SchoolOfstedPages.seo_title(school),
          "seo" => SchoolOfstedPages.seo(school),
          "description" => "The latest Ofsted rating, grades by area and full inspection history for #{SchoolOfstedPages.place(school, gias[school['name']])}.",
          "permalink" => "/cheltenham-schools/#{school['slug']}",
          "type" => "property",
          "schema" => "school-ofsted"
        )
        site.pages << page
      end
    end
  end
end
