const copyButton = document.querySelector('#copy-command')
const commands = document.querySelector('#compose-command')
const status = document.querySelector('#copy-status')
let resetLabel

if (navigator.clipboard) {
  copyButton.hidden = false
  copyButton.addEventListener('click', async () => {
    clearTimeout(resetLabel)
    try {
      await navigator.clipboard.writeText(commands.textContent)
      copyButton.textContent = 'Copied'
      status.textContent = 'Installation commands copied.'
    } catch {
      const selection = window.getSelection()
      const range = document.createRange()
      range.selectNodeContents(commands)
      selection.removeAllRanges()
      selection.addRange(range)
      copyButton.textContent = 'Commands selected'
      status.textContent = 'Use your browser’s copy command to copy the selection.'
    }
    resetLabel = setTimeout(() => {
      copyButton.textContent = 'Copy commands'
      status.textContent = ''
    }, 2500)
  })
}
