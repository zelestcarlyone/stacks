# Changelog

## [1.0.3]

### Features

- Refectored large parts of the downloader:
  - Added ability to use Flaresolverr
  - Updated the download logic to better catch download links
  - Downloads are randomized to spread load across multiple servers
- Added the ability to disable authentification
- Removed alerts and replaced them with a new toast system

### Minor changes

- Added cashe busting to script and css

### Architecture

- Broke out everything into modules
- Config file now works through a self-regenerating schema that validates the config on load and fixes errors on the fly

## [1.0.2] - 2025-11-18

### Hotfix

- Fixed issue where slow downloads sometimes would return bin-files instead of the actual downloads

## [1.0.1] - 2025-11-18

### Hotfix

- Fixed issue where some scraped mirrors would be relative instead of absolute, making downloads fail

## [1.0.0] - 2025-11-19

- Initial stable release
