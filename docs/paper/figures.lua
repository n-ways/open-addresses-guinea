-- In the PDF a figure uses its vector PDF; the markdown on the web uses the SVG.
function Image(img)
  img.src = img.src:gsub('%.svg$', '.pdf')
  return img
end

-- An unnumbered chapter (availability, acknowledgements, references) sets its own running head;
-- \section* would otherwise leave the previous chapter's title at the top of its pages.
function Header(h)
  if h.level == 1 and h.classes:includes('unnumbered') then
    local title = pandoc.utils.stringify(h.content)
    return {h, pandoc.RawBlock('latex', '\\markboth{' .. title .. '}{' .. title .. '}')}
  end
end
