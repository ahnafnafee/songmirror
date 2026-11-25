export const siteUrl = 'https://songmirror.ahnafnafee.dev/'
export const sitemapUrl = new URL('sitemap.xml', siteUrl).href
export const searchPages = [siteUrl, new URL('trailer/', siteUrl).href]

// This is the public IndexNow verification file, not an account credential.
export const indexNowKey = '1c3d954a07d944df87bc93921de5af64'
export const keyLocation = new URL(`${indexNowKey}.txt`, siteUrl).href
