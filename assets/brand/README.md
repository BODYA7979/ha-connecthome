# ConnectHome brand images

These SVG layouts preserve the original logo's alpha mask from the root
`icon.png`. That original image remains unchanged as the source artwork.

- `icon.svg`: white house/radio symbol on a rounded `#3d5ba7` tile.
- `logo.svg`: full wordmark for light backgrounds.
- `dark_logo.svg`: full wordmark for dark backgrounds.

Render the SVGs with a transparent background to the corresponding PNGs in
`custom_components/connecthome/brand/`. The regular icon is 256×256 and its
`@2x` version is 512×512. Regular logos are 610×128 and their `@2x` versions
are 1220×256. Keep each logo's aspect ratio when rendering.

The blue tile works in both themes, so it does not need duplicate `dark_icon`
files. Home Assistant uses `icon.png` and `icon@2x.png` as their fallbacks.
Local brand images require Home Assistant 2026.3 or later; see the
[Home Assistant brand images documentation](https://contributors.home-assistant.io/blog/2026/02/24/brands-proxy-api/).
