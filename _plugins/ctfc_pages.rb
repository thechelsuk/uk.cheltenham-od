# frozen_string_literal: true

# Cheltenham Town's league history pages, generated from the files that
# _python/ctfc-results.py writes:
#
#   /cheltenham-sports/cheltenham-town-fc/record/<season>   each season's league table, from 2000-01
#   /cheltenham-sports/cheltenham-town-fc/vs/<club>         the record against each opponent
#   /cheltenham-sports/cheltenham-town-fc/referees/<name>   the record under each referee
#
# They hang off the Cheltenham Town FC page through `parent:`, so they stay out
# of the menu and the sponsor table. A new opponent, referee or season gets its
# page on the next build without a front-matter file.

module CtfcPages
  SEO_LIMIT = 160
  TITLE_LIMIT = 60
  HUB = "/cheltenham-sports/cheltenham-town-fc"
  STATS_FROM = "2000-01"

  module_function

  def fit(options, limit)
    options.find { |text| text.length <= limit } || options.last
  end

  # The "In this section" row on every history page: the same four links, named in full so the site's
  # short-name rule (which drops a leading "Cheltenham ") never turns them into "Town ...".
  SECTIONS = [
    ["Fixtures and Results", HUB],
    ["Season by Season", "#{HUB}/record"],
    ["Opponents", "#{HUB}/vs"],
    ["Referees", "#{HUB}/referees"],
  ].freeze

  def family(current)
    SECTIONS.map { |name, url| { "name" => name, "url" => url, "current" => url == current } }
  end

  def page(site, dir, slug, data)
    page = Jekyll::PageWithoutAFile.new(site, site.source, dir.delete_prefix("/"), "#{slug}.html")
    page.data.merge!({ "type" => "activities", "parent" => HUB, "family" => family(dir) }.merge(data))
    site.pages << page
  end

  class Generator < Jekyll::Generator
    safe true
    priority :normal

    def generate(site)
      seasons(site)
      opponents(site)
      referees(site)
      site.pages.each do |p|
        url = p.url.to_s.delete_suffix(".html").delete_suffix("/")
        p.data["family"] = CtfcPages.family(url) if CtfcPages::SECTIONS[1..].any? { |_, u| u == url }
      end
    end

    def seasons(site)
      (site.data["ctfc-seasons"] || {}).each do |key, s|
        next if key < STATS_FROM

        span = s["season_display"]
        division = s["division"]
        CtfcPages.page(site, "#{HUB}/record", key,
                       "layout" => "things-to-do/ctfc-season",
                       "season" => key,
                       "title" => "#{division} #{span}: #{s['complete'] ? 'Final' : 'Current'} Table and Cheltenham Town's Season",
                       "seo_title" => CtfcPages.fit(["#{division} #{span} Table: Cheltenham Town",
                                                     "#{division} #{span} Table"], CtfcPages::TITLE_LIMIT),
                       "seo" => CtfcPages.fit(["The #{division} table for #{span}, with points per game, and every Cheltenham Town league match that season with half-time scores, referees and match stats.",
                                               "The #{division} table for #{span} and Cheltenham Town's league matches that season."],
                                              CtfcPages::SEO_LIMIT),
                       "description" => "The #{s['complete'] ? 'final' : 'current'} #{division} table for #{span}, and every league match Cheltenham Town played that season.",
                       "permalink" => "#{HUB}/record/#{key}",
                       "parent" => HUB)
      end
    end

    def opponents(site)
      (site.data["ctfc-opponents"] || {}).each do |slug, o|
        club = o["club"]
        CtfcPages.page(site, "#{HUB}/vs", slug,
                       "layout" => "things-to-do/ctfc-opponent",
                       "opponent" => slug,
                       "title" => "Cheltenham Town vs #{club}: Head-to-Head Record",
                       "seo_title" => CtfcPages.fit(["Cheltenham Town vs #{club}: Head-to-Head",
                                                     "Cheltenham vs #{club}: Head-to-Head",
                                                     "Cheltenham vs #{club}"], CtfcPages::TITLE_LIMIT),
                       "seo" => CtfcPages.fit(["Cheltenham Town's league record against #{club}: every meeting since 2000, home and away, half-time scores, cards, shots and referees.",
                                               "Cheltenham Town's league record against #{club}: every meeting since 2000."],
                                              CtfcPages::SEO_LIMIT),
                       "description" => "Every league meeting between Cheltenham Town and #{club} since 2000–01, with the head-to-head record, half-time scores and match stats.",
                       "permalink" => "#{HUB}/vs/#{slug}",
                       "parent" => HUB)
      end
    end

    def referees(site)
      (site.data.dig("ctfc-referees", "referees") || []).each do |r|
        name = r["name"]
        CtfcPages.page(site, "#{HUB}/referees", r["slug"],
                       "layout" => "things-to-do/ctfc-referee",
                       "referee" => r["slug"],
                       "title" => "Cheltenham Town's Record With Referee #{name}",
                       "seo_title" => CtfcPages.fit(["Cheltenham Town's Record With Referee #{name}",
                                                     "Cheltenham Town With Referee #{name}",
                                                     "Cheltenham Town: Referee #{name}"], CtfcPages::TITLE_LIMIT),
                       "seo" => CtfcPages.fit(["Cheltenham Town's league record in matches refereed by #{name}: wins, draws, defeats, points per game, and yellow and red cards for both sides.",
                                               "Cheltenham Town's league record with referee #{name}."], CtfcPages::SEO_LIMIT),
                       "description" => "Every Cheltenham Town league match refereed by #{name} since 2000–01, with the record, points per game and cards for both sides.",
                       "permalink" => "#{HUB}/referees/#{r['slug']}",
                       "parent" => HUB)
      end
    end
  end
end
