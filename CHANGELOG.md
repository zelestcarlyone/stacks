# Changelog

## [1.1.0]

### Features

- Added a bar for adding downloads manually
- Added the ability to disable authentification
- Log console added to front-end
- Made shutdowns more graceful
- Refectored the downloader completely:
  - Added ability to use Flaresolverr and warm cookies for downloader
  - Per-domain cookie caching system - each mirror gets its own cookie file for reuse
  - Updated the download logic to better catch download links
  - Downloads are randomized to spread load across multiple servers
  - Downloader identifies files files that are unreasonably small and tries next server
  - Added a more secure way of finding the correct file name
  - More information on the status page about what's happening with a download
  - Added MD5 checksum verification for all downloads
  - Real-time status updates showing mirror progress and download stages
- Removed alerts and replaced them with a new toast system
- Stacks Extension Updated
  - Added ability to make sure it is the latest version compared to the server
  - Updated layout to better mimic the Stacks Frontend
- Added in Flaresolverr to the installation example

### Minor changes

- Added cashe busting to script and css

### Architecture

- Config file now works through a self-regenerating schema that validates the config on load and fixes errors on the fly
- Broke out everything into modules
- Switched from CSS to SCSS for maintainability

### Bug fixes
- The way file names are grabbed are now more robust and we should have no files named "Anna's Archive" or "Unknown" anymore.

## [1.0.2] - 2025-11-18

### Hotfix

- Fixed issue where slow downloads sometimes would return bin-files instead of the actual downloads

## [1.0.1] - 2025-11-18

### Hotfix

- Fixed issue where some scraped mirrors would be relative instead of absolute, making downloads fail

## [1.0.0] - 2025-11-19

- Initial stable release
