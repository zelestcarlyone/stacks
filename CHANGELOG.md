# Changelog

## [1.1.0]

### Features

- Added a bar for adding downloads manually
- Added the ability to disable authentification
- Log console added to front-end
- Made shutdowns more graceful
- Refectored large parts of the downloader:
  - Added ability to use Flaresolverr
  - Updated the download logic to better catch download links
  - Downloads are randomized to spread load across multiple servers
  - Downloader identifies files files that are unreasonably small and tries next server
  - Added a more secure way of finding the correct file name
- Removed alerts and replaced them with a new toast system

### Minor changes

- Added cashe busting to script and css

### Architecture

- Config file now works through a self-regenerating schema that validates the config on load and fixes errors on the fly
- Broke out everything into modules
- Switched from CSS to SCSS for maintainability

## [1.0.2] - 2025-11-18

### Hotfix

- Fixed issue where slow downloads sometimes would return bin-files instead of the actual downloads

## [1.0.1] - 2025-11-18

### Hotfix

- Fixed issue where some scraped mirrors would be relative instead of absolute, making downloads fail

## [1.0.0] - 2025-11-19

- Initial stable release
