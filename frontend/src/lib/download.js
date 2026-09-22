/** 컷 이미지들을 기기에 내려받는다. <a href> 다이렉트 링크만 쓰면 오리진이 다를 때
 *  download 속성이 무시돼 새 탭으로 열리기만 한다 — fetch로 blob을 받아서 내려받는다.
 *  여러 장을 한꺼번에 a.click()하면 브라우저가 팝업/다운로드로 오인해 일부만 받아지는
 *  경우가 있어, 한 장씩 약간의 간격을 두고 순서대로 받는다.
 *  @returns {Promise<boolean>} 받을 이미지가 있어서 시도했는지(하나라도 실패해도 true).
 */
export async function downloadImages(cuts, baseName) {
  const done = (cuts || []).filter((c) => c.status === 'done' && c.image);
  if (!done.length) return false;

  const name = (baseName || '광고').replace(/[\\/:*?"<>|]/g, '').trim() || '광고';

  for (const c of done) {
    try {
      const res = await fetch(c.image);
      const blob = await res.blob();
      const ext = (blob.type.split('/')[1] || 'png').split('+')[0];
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${name}_${c.n}컷.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // 한 장이 실패해도 나머지는 계속 받는다.
    }
    // eslint-disable-next-line no-await-in-loop
    await new Promise((r) => setTimeout(r, 300));
  }
  return true;
}
