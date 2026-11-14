// Set the stored theme before React paints, under the app's script policy.
try {
  if (localStorage.getItem('songmirror-theme') !== 'light') {
    document.documentElement.classList.add('dark')
  }
} catch {
  document.documentElement.classList.add('dark')
}
