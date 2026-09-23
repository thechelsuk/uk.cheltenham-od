# frozen_string_literal: true

# Data freshness for the local admin page.
#
# For every data file listed in _data/sources.json, finds when its content
# last changed (the date of the last git commit that touched it) and flags it
# as stale when that is older than its schedule allows. The scheduled
# workflows let a failing fetcher fail quietly, so this is the sense check
# that its data has stopped updating.
#
# Only runs when the admin page (admin.md, which is local and gitignored) is
# part of the build, so the published site is never slowed by it. The result
# is site.data["data_freshness"], one row per source file.

require "json"
require "open3"
require "time"

module DataFreshness
  # Top-level fields a fetcher rewrites on every successful run.
  RUN_STAMPS = %w(generated_at updated updated_iso last_updated).freeze

  # How long a file may go without changing before it is flagged. Generous on
  # purpose: a source can be healthy and simply have nothing new to report.
  STALE_AFTER_DAYS = {
    "every 5 minutes" => 2,
    "hourly" => 2,
    "every two hours" => 2,
    "daily" => 4,
    "monthly" => 45,
  }.freeze

  module_function

  def last_changed(root, path)
    out, status = Open3.capture2("git", "-C", root, "log", "-1", "--format=%cI", "--", path)
    status.success? && !out.strip.empty? ? Time.iso8601(out.strip) : nil
  rescue StandardError
    nil
  end

  # True when the file carries a per-run timestamp, so it changes on every
  # successful run; a list or raw feed only changes when its data does.
  def stamped?(root, path)
    data = JSON.parse(File.read(File.join(root, path), encoding: "UTF-8"))
    data.is_a?(Hash) && RUN_STAMPS.any? { |key| data.key?(key) }
  rescue StandardError
    false
  end

  # ok, manual or unknown; past its threshold a stamped file is "stale" (its
  # fetcher has stopped succeeding) and any other file "unchanged" (its data
  # may simply not have changed).
  def status(changed, schedule, now, stamped)
    return "manual" unless STALE_AFTER_DAYS.key?(schedule)
    return "unknown" unless changed
    return "ok" if (now - changed) / 86_400 <= STALE_AFTER_DAYS[schedule]

    stamped ? "stale" : "unchanged"
  end

  def rows(site, now = Time.now)
    Array(site.data["sources"]).flat_map do |source|
      Array(source["data"]).map do |item|
        changed = last_changed(site.source, item["file"])
        {
          "id" => source["id"],
          "name" => source["name"] || source["id"],
          "source_url" => source["source_url"],
          "licence_type" => source["licence_type"],
          "file" => item["file"],
          "schedule" => item["schedule"],
          "last_changed" => changed&.iso8601,
          "age_days" => changed ? ((now - changed) / 86_400).floor : nil,
          "status" => status(changed, item["schedule"], now, stamped?(site.source, item["file"])),
        }
      end
    end
  end

  def admin_build?(site)
    site.pages.any? { |page| page.name == "admin.md" }
  end
end

Jekyll::Hooks.register :site, :post_read do |site|
  next unless DataFreshness.admin_build?(site)

  site.data["data_freshness"] = DataFreshness.rows(site)
end
