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

  def last_changed(site)
    dates = {}
    stamp = nil
    git(site, "log", "--format=@%cI", "--name-only", "--", "_data").each_line do |line|
      line = line.strip
      if line.start_with?("@")
        stamp = line[1..]
      elsif !line.empty? && stamp && !dates.key?(line)
        dates[line] = stamp
      end
    end
    git(site, "status", "--porcelain", "--", "_data").each_line do |line|
      path = line[3..].to_s.strip.split(" -> ").last
      full = File.join(site.source, path.to_s)
      dates[path] = File.mtime(full).iso8601 if path && File.file?(full)
    end
    dates
  end
end

Jekyll::Hooks.register :site, :post_read do |site|
  site.data["freshness"] = DataFreshness.last_changed(site)
end
