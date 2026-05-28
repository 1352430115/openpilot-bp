# BluePilot Web Routes Panel

Modern web interface for browsing and playing route videos directly in your browser.

## Features

- Browse all routes with metadata (duration, size, segments)
- Star/favorite routes
- Native HEVC video playback in modern browsers
- Multi-camera support (front, wide, driver)
- Responsive design for mobile and desktop
- Automatic segment transitions
- Delete routes from web interface

## Building

The UI is a React + Vite app. **System `npm` is not required** — use the bundled build script (downloads portable Node on first run):

```bash
cd bluepilot/web
./build.sh
```

Output goes to `public/`, which the portal server on port 8088 serves.

If you already have Node 18+ and npm installed:

```bash
cd bluepilot/web
npm ci
npm run build
```

## Development

The web app is built with vanilla JavaScript (no frameworks) for simplicity and small size.

### Files

- `src/index.html` - Main HTML structure
- `src/styles.css` - BluePilot-themed CSS
- `src/app.js` - Application logic
- `public/` - Compiled/deployed files (committed to repo)

## Browser Compatibility

- **Safari (iOS/macOS)**: Full support including HEVC playback
- **Chrome/Edge**: Partial HEVC support (depends on device)
- **Firefox**: Limited HEVC support

## API Endpoints

See the backend server for API documentation.
