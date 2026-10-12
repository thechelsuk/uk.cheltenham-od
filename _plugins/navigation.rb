# frozen_string_literal: true

# The site's structure: menu, category pages, breadcrumbs and the
# "In this section" links, all from _data/navigation/*.yml.
#
# One file per category, read in `position` order:
#
#   group: "Getting Around"          the category's name (its page sets `group:` to match)
#   position: 1                      menu column order
#   subgroups:                       headings on the category page, in order
#     - name: "Driving & Parking"
#       items:                       main pages: a menu entry each
#         - name: "Cheltenham Car Parks"
#           link: /cheltenham-car-parks
#           description: "..."
#           short: "Car Parks"       optional: the name in breadcrumbs, section rows and the
#                                    footer, when dropping "Cheltenham" still leaves it long
#           children:                sub-pages: not in the menu, listed under their parent
#             - name: "..."
#               link: ...
#               description: "..."
#               short: "..."         optional, as above
#               a_z: true            also list it in the footer's Pages (A-Z)
#
# A page can belong to a category without a menu entry by setting, in its
# front matter, `section:` (the category), `subgroup:` (its heading there)
# and optionally `nav_title:` (a shorter name) and `parent:` (the link of
# the page it sits under). Any other page that only needs a breadcrumb,
# such as a ward profile or a care home, sets just `parent:`.
#
# The plugin rebuilds the flat `site.navigation_header` list the templates
# have always read (each item gains `group` and `subgroup`), fills the
# footer's Pages (A-Z) links, and gives every page in the structure:
#   page.breadcrumbs  [{"name", "url"}, ...] from Home down to its parent
#   page.family       [{"name", "url", "current"}, ...] its parent and sub-pages
# and `site.navigation_groups`, the menu: [{"name", "url", "type", "subgroups" => [{"name", "items"}]}].
# Data files reload while `jekyll serve` runs; _config.yml does not.

module Navigation
  module_function

  def norm(url)
    url = url.to_s.sub(/\.html\z/, "").sub(%r{/index\z}, "/")
    url.length > 1 ? url.chomp("/") : url
  end

  # The display name: an explicit short name, or the name without "Cheltenham"
  # and, for a sub-page, without its parent's name ("Crime Data 2025" -> "2025").
  def short(name, parent = nil, explicit = nil)
    return explicit if explicit

    name = name.to_s.sub(/\ACheltenham /, "")
    return name unless parent

    rest = name.delete_prefix("#{parent} ")
    rest.empty? || rest == name ? name : rest
  end

  def groups(site)
    files = (site.data["navigation"] || {}).values.select { |g| g.is_a?(Hash) && g["group"] }
    files.sort_by { |g| g["position"].to_i }
  end

  def flatten(groups)
    groups.flat_map do |g|
      (g["subgroups"] || []).flat_map do |sg|
        (sg["items"] || []).map { |item| item.merge("group" => g["group"], "subgroup" => sg["name"]) }
      end
    end
  end

  def section_pages(site)
    site.pages.select { |p| p.data["section"] }
  end

  def nodes(site, items)
    map = {}
    items.each do |item|
      map[norm(item["link"])] = {
        "name" => item["name"], "short" => item["short"], "parent" => nil, "group" => item["group"]
      }
      (item["children"] || []).each do |child|
        map[norm(child["link"])] = {
          "name" => child["name"], "short" => child["short"], "parent" => norm(item["link"]), "group" => item["group"]
        }
      end
    end
    section_pages(site).each do |p|
      parent = p.data["parent"] ? norm(p.data["parent"]) : nil
      map[norm(p.url)] ||= {
        "name" => p.data["nav_title"] || p.data["title"], "parent" => parent, "group" => p.data["section"]
      }
    end
    map
  end

  # The footer's Pages (A-Z): short names, sorted ignoring a leading "The".
  def a_z(site, items)
    links = items.flat_map do |item|
      [item] + (item["children"] || []).select { |c| c["a_z"] }
    end
    links = links.map { |i| { "name" => short(i["name"], nil, i["short"]), "link" => i["link"] } }
    links += section_pages(site).map do |p|
      { "name" => short(p.data["nav_title"] || p.data["title"]), "link" => norm(p.url) }
    end
    links.sort_by { |l| l["name"].sub(/\AThe /, "").downcase }
  end

  def link(node_url, map)
    node = map[node_url]
    parent = node["parent"] && map[node["parent"]]
    parent_name = parent && short(parent["name"], nil, parent["short"])
    { "name" => short(node["name"], parent_name, node["short"]), "url" => node_url }
  end

  def family(url, map)
    node = map[url]
    head = node["parent"] || url
    kids = map.select { |_, n| n["parent"] == head }.keys
    return [] if kids.empty?

    ([head] + kids).map do |u|
      entry = u == head ? { "name" => short(map[u]["name"], nil, map[u]["short"]), "url" => u } : link(u, map)
      entry.merge("current" => u == url)
    end
  end

  def crumbs(url, map, categories)
    chain = []
    up = map[url]["parent"]
    while up && map[up] && chain.length < 4
      chain.unshift(up)
      up = map[up]["parent"]
    end
    home = [{ "name" => "Home", "url" => "/" }]
    category = categories[map[url]["group"]]
    home += [{ "name" => map[url]["group"], "url" => category }] if category
    home + chain.map { |u| link(u, map) }
  end

  def apply(site)
    items = flatten(groups(site))
    site.config["navigation_header"] = items
    site.config["footer_pages"] = (site.config["footer_pages"] || {}).merge("links" => a_z(site, items))

    map = nodes(site, items)
    category_pages = site.pages.select { |p| p.data["group"] && p.data["layout"] == "explore-category" }
    categories = category_pages.to_h { |p| [p.data["group"], norm(p.url)] }
    site.config["navigation_groups"] = menu(site, items, category_pages)
    pages = site.pages + site.collections.values.flat_map(&:docs)
    pages.each do |p|
      url = norm(p.url)
      if p.data["layout"] == "explore-category"
        p.data["breadcrumbs"] = [{ "name" => "Home", "url" => "/" }]
      elsif map[url]
        p.data["breadcrumbs"] = crumbs(url, map, categories)
        p.data["family"] = family(url, map)
      elsif p.data["parent"]
        p.data["breadcrumbs"] = parent_crumbs(norm(p.data["parent"]), map, categories, pages)
      elsif standalone?(p, url)
        p.data["breadcrumbs"] = [{ "name" => "Home", "url" => "/" }]
      end
    end
  end

  # Any other page that opens with the usual header (About, Policies, Feeds...)
  # gets just "Home", so every page but the home page starts the same way.
  def standalone?(page, url)
    layout = page.data["layout"].to_s
    return false if layout.empty? || %w[redirect empty].include?(layout)

    !(url == "/" || url == "/404" || url.start_with?("/admin", "/form"))
  end

  # The menu, worked out once per build rather than on every page: each
  # category with its page's link and theme, and its subgroups' items.
  def menu(site, items, category_pages)
    groups(site).map do |g|
      page = category_pages.find { |p| p.data["group"] == g["group"] }
      subgroups = (g["subgroups"] || []).map do |sg|
        sg_items = items.select { |i| i["group"] == g["group"] && i["subgroup"] == sg["name"] }
        { "name" => sg["name"], "items" => sg_items }
      end
      url = page && norm(page.url)
      { "name" => g["group"], "url" => url, "type" => page&.data&.dig("type"), "subgroups" => subgroups }
    end
  end

  # For a page outside the structure: the trail to its parent, or Home and
  # the parent page's title when the parent is outside it too (a newsletter).
  def parent_crumbs(parent, map, categories, pages)
    return crumbs(parent, map, categories) + [link(parent, map)] if map[parent]

    page = pages.find { |p| norm(p.url) == parent }
    return nil unless page

    name = short(page.data["nav_title"] || page.data["title"])
    [{ "name" => "Home", "url" => "/" }, { "name" => name, "url" => parent }]
  end

  # Runs last, so pages made by other generators (care homes, schools) are included.
  class Generator < Jekyll::Generator
    safe true
    priority :lowest

    def generate(site)
      Navigation.apply(site)
    end
  end
end
