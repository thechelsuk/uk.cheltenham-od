# frozen_string_literal: true

# When each _data file last changed, for the "Last updated" line under every
# data page (_includes/freshness.html).
#
# The date is the last commit that changed the file, so it moves only when
# the data itself changes, not each time a fetcher runs and finds nothing new
# (helper.write_json leaves an unchanged file alone). One `git log` pass
# covers every file. A file with uncommitted changes, as when previewing
# locally, uses its modified time instead.
#
# The result is site.data["freshness"]: {"_data/car-parks.json" => "2026-10-12T05:43:14+01:00", ...}.
#
# The same dates give each page its sitemap <lastmod> (page.sitemap_lastmod):
# the later of when its own file last changed and when any data file it shows
# last changed, using the "pages" each source lists in _data/sources.json.
# A page with no data of its own, like a care home or ward profile made from
# its parent's data, uses its parent's sources. Pages with no date at all get
# no lastmod rather than a guessed one.
# The deploy workflow checks out the full history (fetch-depth: 0) so the
# dates are right; on a shallow checkout every file would show the latest
# commit's date.

require "open3"
require "time"

module DataFreshness
  module_function

  def git(site, *args)
    out, status = Open3.capture2("git", "-C", site.source, *args)
    status.success? ? out : ""
  rescue Errno::ENOENT
    ""
  end

  def last_changed(site, *paths)
    paths = ["_data"] if paths.empty?
    dates = {}
    stamp = nil
    git(site, "log", "--format=@%cI", "--name-only", "--", *paths).each_line do |line|
      line = line.strip
      if line.start_with?("@")
        stamp = line[1..]
      elsif !line.empty? && stamp && !dates.key?(line)
        dates[line] = stamp
      end
    end
    git(site, "status", "--porcelain", "--", *paths).each_line do |line|
      path = line[3..].to_s.strip.split(" -> ").last
      full = File.join(site.source, path.to_s)
      dates[path] = File.mtime(full).iso8601 if path && File.file?(full)
    end
    dates
  end

  def norm(url)
    url = url.to_s.sub(/\.html\z/, "").sub(%r{/index\z}, "/")
    url.length > 1 ? url.chomp("/") : url
  end

  # Data files shown on each page, from the "pages" in _data/sources.json.
  def page_data_files(site)
    files = Hash.new { |h, k| h[k] = [] }
    (site.data["sources"] || []).each do |source|
      data = (source["data"] || []).map { |d| d["file"] }
      (source["pages"] || []).each { |page| files[norm(page)].concat(data) }
    end
    files
  end

  def sitemap_dates(site)
    data_dates = site.data["freshness"] || {}
    page_dates = last_changed(site, "_pages")
    files = page_data_files(site)
    site.pages.each do |page|
      dates = [page_dates[page.relative_path]]
      shown = files[norm(page.url)]
      # A page made from its parent's data, like a care home or ward profile.
      shown += files[norm(page.data["parent"])] if shown.empty? && page.data["parent"]
      dates += shown.map { |f| data_dates[f] }
      latest = dates.compact.max_by { |d| Time.parse(d) }
      page.data["sitemap_lastmod"] = latest if latest
    end
  end

  # Runs after the other generators, so it sees the pages they make.
  class Generator < Jekyll::Generator
    safe true
    priority :lowest

    def generate(site)
      DataFreshness.sitemap_dates(site)
    end
  end
end

Jekyll::Hooks.register :site, :post_read do |site|
  site.data["freshness"] = DataFreshness.last_changed(site)
end
