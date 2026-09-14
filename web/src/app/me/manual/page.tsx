'use client'

import { useEffect, useState } from 'react'
import { PageHeader } from '@/components/ui/PageHeader'

// KBKOREA 利用マニュアル（会員ログインの内側）。日本語⇄韓国語トグル。
// 内容は自己完結（スタイルは .manual-root 配下にスコープ）。単一ソースとしてここに保持する。

const MANUAL_CSS = `
.manual-root{
  --m-surface:#10141c; --m-surface2:#161b25; --m-surface3:#1c2230;
  --m-text:#e6ecf3; --m-muted:#8b97a9; --m-dim:#6b7d97;
  --m-cyan:#5cdfff; --m-cyan-dim:#3a8fa5; --m-amber:#ffb547; --m-amber-dim:#a37130;
  --m-win:#3fd49a; --m-border:#232b38;
  color:var(--m-text); font-size:15px; line-height:1.75;
}
.manual-root .flow{background:var(--m-surface); border:1px solid var(--m-border); border-radius:12px; padding:18px 20px; margin:18px 0; font-family:ui-monospace,Consolas,monospace; color:var(--m-cyan); font-size:14px; line-height:2; white-space:pre; overflow-x:auto;}
.manual-root h2{font-size:21px; margin:44px 0 14px; padding-top:16px; border-top:1px solid var(--m-border); display:flex; align-items:center; gap:10px;}
.manual-root h2 .num{display:inline-flex; align-items:center; justify-content:center; min-width:30px; height:30px; padding:0 6px; border-radius:8px; background:var(--m-cyan); color:#04121a; font-size:15px; font-weight:800;}
.manual-root h3{font-size:16px; margin:26px 0 8px; color:var(--m-text);}
.manual-root h3 .lbl{display:inline-block; background:var(--m-surface3); color:var(--m-cyan); border:1px solid var(--m-border); border-radius:6px; padding:1px 8px; font-size:13px; font-family:ui-monospace,Consolas,monospace; margin-right:6px;}
.manual-root p{margin:10px 0;}
.manual-root ul,.manual-root ol{margin:10px 0; padding-left:22px;}
.manual-root li{margin:5px 0;}
.manual-root code{background:var(--m-surface3); border:1px solid var(--m-border); border-radius:5px; padding:1px 6px; font-size:13px; font-family:ui-monospace,Consolas,monospace; color:var(--m-amber);}
.manual-root .card{background:var(--m-surface); border:1px solid var(--m-border); border-radius:12px; padding:16px 18px; margin:14px 0;}
.manual-root table{width:100%; border-collapse:collapse; margin:14px 0; font-size:14px; overflow:hidden; border-radius:10px; border:1px solid var(--m-border);}
.manual-root th,.manual-root td{text-align:left; padding:10px 12px; border-bottom:1px solid var(--m-border); vertical-align:top;}
.manual-root th{background:var(--m-surface2); color:var(--m-muted); font-weight:600; font-size:12.5px;}
.manual-root tr:last-child td{border-bottom:none;}
.manual-root td:first-child{font-weight:600;}
.manual-root .tag{display:inline-block; padding:1px 8px; border-radius:6px; font-size:12px; font-weight:700;}
.manual-root .ok{background:rgba(63,212,154,.15); color:var(--m-win);}
.manual-root .callout{border-radius:10px; padding:12px 16px; margin:14px 0; border:1px solid var(--m-border); background:var(--m-surface2);}
.manual-root .callout.warn{border-color:var(--m-amber-dim); background:rgba(255,181,71,.08);}
.manual-root .callout.warn b{color:var(--m-amber);}
.manual-root .callout.tip{border-color:var(--m-cyan-dim); background:rgba(92,223,255,.07);}
.manual-root .callout.tip b{color:var(--m-cyan);}
.manual-root .callout .ic{font-weight:800; margin-right:6px;}
.manual-root .checklist{list-style:none; padding-left:0;}
.manual-root .checklist li{padding-left:28px; position:relative; margin:8px 0;}
.manual-root .checklist li:before{content:"\\2610"; position:absolute; left:0; color:var(--m-cyan); font-size:17px;}
.manual-root .m-footer{margin-top:50px; padding-top:20px; border-top:1px solid var(--m-border); color:var(--m-dim); font-size:12.5px;}
.manual-root [data-lang]{display:none;}
.manual-root.lang-ja [data-lang="ja"]{display:block;}
.manual-root.lang-ko [data-lang="ko"]{display:block;}
.manual-root th[data-lang],.manual-root td[data-lang],.manual-root span[data-lang],.manual-root li[data-lang],.manual-root b[data-lang]{display:none;}
.manual-root.lang-ja th[data-lang="ja"],.manual-root.lang-ja td[data-lang="ja"],.manual-root.lang-ja span[data-lang="ja"],.manual-root.lang-ja li[data-lang="ja"],.manual-root.lang-ja b[data-lang="ja"]{display:revert;}
.manual-root.lang-ko th[data-lang="ko"],.manual-root.lang-ko td[data-lang="ko"],.manual-root.lang-ko span[data-lang="ko"],.manual-root.lang-ko li[data-lang="ko"],.manual-root.lang-ko b[data-lang="ko"]{display:revert;}
.manual-root.lang-ja h2 span[data-lang="ja"],.manual-root.lang-ja h3 span[data-lang="ja"]{display:inline;}
.manual-root.lang-ko h2 span[data-lang="ko"],.manual-root.lang-ko h3 span[data-lang="ko"]{display:inline;}
@media (max-width:560px){ .manual-root .flow{font-size:12px;} }
`

const MANUAL_BODY = `
<div data-lang="ja"><div class="flow">①  インストール（管理者が代行）
        ↓
②  bafather.uk に登録
        ↓
③  GUI 起動 → Chrome が自動で開く → Stake にログイン
        ↓
④  設定する → SAVE → START
        ↓
⑤  監視（不具合は「⑤ 不具合集」へ）</div></div>
<div data-lang="ko"><div class="flow">①  설치（관리자가 대행）
        ↓
②  bafather.uk 회원가입
        ↓
③  GUI 실행 → Chrome 자동 실행 → Stake 로그인
        ↓
④  설정 → SAVE → START
        ↓
⑤  모니터링（문제는 「⑤ 문제 해결」로）</div></div>

<h2><span class="num">①</span><span data-lang="ja">インストール（管理者が代行）</span><span data-lang="ko">설치（관리자가 대행）</span></h2>
<div data-lang="ja">
  <p>インストールは<b>管理者が代行</b>します。利用者は次をするだけです。</p>
  <ol>
    <li><b>管理者にデスクトップクラウドのログイン情報を伝える</b>（接続先アドレス・ユーザー名・パスワード）。
      <div class="callout warn"><span class="ic">⚠️</span><b>チャットの平文で送らないでください。</b>管理者が指定する安全な方法で渡します。</div>
    </li>
    <li>管理者が受け子機（デスクトップクラウド）へリモート接続し、<code>KBKOREA_Setup.exe</code> を実行してインストールします。</li>
    <li>完了するとデスクトップに <b>KBKOREA</b> アイコンができます。</li>
  </ol>
  <div class="callout tip"><span class="ic">💡</span> 1台のデスクトップクラウドにつき GUI は 1つ。複数を同時に動かさないでください。</div>
</div>
<div data-lang="ko">
  <p>설치는 <b>관리자가 대행</b>합니다. 이용자는 다음만 하면 됩니다.</p>
  <ol>
    <li><b>관리자에게 데스크톱 클라우드 로그인 정보를 전달</b>（접속 주소·아이디·비밀번호）.
      <div class="callout warn"><span class="ic">⚠️</span><b>채팅 평문으로 보내지 마세요.</b> 관리자가 지정하는 안전한 방법으로 전달합니다.</div>
    </li>
    <li>관리자가 데스크톱 클라우드에 원격 접속하여 <code>KBKOREA_Setup.exe</code> 를 실행해 설치합니다.</li>
    <li>완료되면 바탕화면에 <b>KBKOREA</b> 아이콘이 생깁니다.</li>
  </ol>
  <div class="callout tip"><span class="ic">💡</span> 데스크톱 클라우드 1대당 GUI는 1개. 여러 개를 동시에 실행하지 마세요.</div>
</div>

<h2><span class="num">②</span><span data-lang="ja">bafather.uk に登録</span><span data-lang="ko">bafather.uk 회원가입</span></h2>
<div data-lang="ja">
  <p>GUI を使うには <b>bafather.uk のアカウント</b>が必要です（ライセンス認証に使います）。</p>
  <ol>
    <li>ブラウザで <code>https://bafather.uk</code> を開く。</li>
    <li><b>招待コード</b>を入力して新規登録（招待コードは管理者から受け取ります）。</li>
    <li>メールアドレス・パスワードを設定 → 確認メールで認証。</li>
    <li>サブスクリプションを有効化。</li>
    <li>登録した<b>メール／パスワード</b>を覚えておく（③でGUIにログイン）。</li>
  </ol>
  <div class="callout tip"><span class="ic">💡</span> メールが届かない時：迷惑メールを確認 → 無ければ管理者に「再送」を依頼。</div>
</div>
<div data-lang="ko">
  <p>GUI를 사용하려면 <b>bafather.uk 계정</b>이 필요합니다（라이선스 인증에 사용）.</p>
  <ol>
    <li>브라우저에서 <code>https://bafather.uk</code> 를 엽니다.</li>
    <li><b>초대 코드</b>를 입력해 회원가입（초대 코드는 관리자에게 받습니다）.</li>
    <li>이메일·비밀번호 설정 → 확인 메일로 인증.</li>
    <li>구독을 활성화합니다.</li>
    <li>등록한 <b>이메일／비밀번호</b>를 기억해 둡니다（③에서 GUI 로그인）.</li>
  </ol>
  <div class="callout tip"><span class="ic">💡</span> 메일이 안 올 때: 스팸함 확인 → 없으면 관리자에게 「재발송」 요청.</div>
</div>

<h2><span class="num">③</span><span data-lang="ja">GUI 起動 → Chrome → Stake ログイン</span><span data-lang="ko">GUI 실행 → Chrome → Stake 로그인</span></h2>
<div data-lang="ja">
  <ol>
    <li>デスクトップの <b>KBKOREA</b> をダブルクリックで起動。</li>
    <li>ログイン画面で、②で登録した <b>bafather.uk のメール／パスワード</b>を入力。</li>
    <li>起動すると <b>BET用のChromeが自動で立ち上がります</b>。</li>
    <li>その<b>自動で開いたChrome</b>で <b>Stakeカジノにログイン</b>。
      <div class="callout warn"><span class="ic">⚠️</span> 必ず<b>ライブバカラの正規ページから</b>入る（ロビーのURLを直接貼らない＝エラーの原因）。</div>
    </li>
    <li>Stakeで <b>ライブバカラ → マルチエリア（複数卓）を手動で開く</b>（KBKOREAは複数卓に賭けるため必須）。</li>
    <li>GUI上部が <b class="tag ok">ONLINE</b> になっていることを確認（<code>OFFLINE</code> なら④の後 START で接続。ダメなら⑤へ）。</li>
  </ol>
</div>
<div data-lang="ko">
  <ol>
    <li>바탕화면의 <b>KBKOREA</b> 를 더블클릭해 실행.</li>
    <li>로그인 화면에서 ②에서 등록한 <b>bafather.uk 이메일／비밀번호</b> 입력.</li>
    <li>실행되면 <b>베팅용 Chrome이 자동으로 열립니다</b>.</li>
    <li>그 <b>자동으로 열린 Chrome</b>에서 <b>Stake 카지노에 로그인</b>.
      <div class="callout warn"><span class="ic">⚠️</span> 반드시 <b>라이브 바카라 정식 페이지에서</b> 진입（로비 URL을 직접 붙여넣지 말 것＝오류 원인）.</div>
    </li>
    <li>Stake에서 <b>라이브 바카라 → 멀티에어리어（여러 테이블）를 수동으로 열기</b>（KBKOREA는 여러 테이블에 베팅하므로 필수）.</li>
    <li>GUI 상단이 <b class="tag ok">ONLINE</b> 인지 확인（<code>OFFLINE</code>이면 ④ 후 START로 연결. 안 되면 ⑤로）.</li>
  </ol>
</div>

<h2><span class="num">④</span><span data-lang="ja">設定について（重要・詳しく）</span><span data-lang="ko">설정（중요·자세히）</span></h2>
<div data-lang="ja">
  <p>歯車の <b>SETTINGS</b> で設定画面を開きます。変更したら<b>必ず SAVE</b>（押さないとサーバーに反映されません）。その後 <b>START</b> で稼働。</p>
  <div class="callout tip"><span class="ic">🔒</span> <b>KBKOREA版のポイント</b><br>・賭け金額（SEQの階段）は<b>サーバーが計算</b>します。受け子機はその額を賭けるだけ。だから資金管理は「SAVEでサーバーへ送信 → サーバーが計算」の流れです。<br>・パターン名は伏せてあり画面は <b>Set A / Set B</b> 表示。<br>・開発用の <b>SIGNAL PANEL は非表示</b>（韓国版では出ません。正常です）。</div>
</div>
<div data-lang="ko">
  <p>톱니바퀴 <b>SETTINGS</b> 로 설정 화면을 엽니다. 변경 후에는 <b>반드시 SAVE</b>（누르지 않으면 서버에 반영되지 않음）. 그다음 <b>START</b> 로 가동.</p>
  <div class="callout tip"><span class="ic">🔒</span> <b>KBKOREA 버전 포인트</b><br>·베팅 금액（SEQ 사다리）은 <b>서버가 계산</b>합니다. 수신 PC는 그 금액을 베팅만. 그래서 자금관리는 「SAVE로 서버 전송 → 서버가 계산」 흐름입니다.<br>·패턴명은 숨겨져 화면에는 <b>Set A / Set B</b> 표시.<br>·개발용 <b>SIGNAL PANEL은 숨김</b>（한국 버전에서는 표시되지 않음. 정상）.</div>
</div>

<h3><span class="lbl">BET MODE</span><span data-lang="ja">賭け方の基本モード</span><span data-lang="ko">기본 베팅 모드</span></h3>
<div data-lang="ja"><table><tr><th>画面表示</th><th>意味</th><th>初心者</th></tr>
<tr><td>Dual-Line Assist</td><td>予告を出し手動補助しつつ賭ける半自動</td><td>△</td></tr>
<tr><td>Dual-Line Auto</td><td>信号が出たら<b>自動</b>でBET（基本）</td><td><span class="tag ok">✅ これ</span></td></tr>
<tr><td>Dual-Line Auto + Follow</td><td>自動BET＋追従も自動（上級）</td><td>△</td></tr></table><p>初心者は <b>Dual-Line Auto</b>。</p></div>
<div data-lang="ko"><table><tr><th>화면 표시</th><th>의미</th><th>초보자</th></tr>
<tr><td>Dual-Line Assist</td><td>예고를 내고 수동 보조하며 베팅하는 반자동</td><td>△</td></tr>
<tr><td>Dual-Line Auto</td><td>신호가 나오면 <b>자동</b>으로 BET（기본）</td><td><span class="tag ok">✅ 이것</span></td></tr>
<tr><td>Dual-Line Auto + Follow</td><td>자동 BET＋팔로우도 자동（상급）</td><td>△</td></tr></table><p>초보자는 <b>Dual-Line Auto</b>.</p></div>

<h3><span class="lbl">Signal set</span><span data-lang="ja">信号セット</span><span data-lang="ko">신호 세트</span></h3>
<div data-lang="ja"><p><b>Set A</b>＝6パターン系 / <b>Set B</b>＝10パターン系。<b>どちらか一方</b>を選択。指示がなければ管理者に確認。</p></div>
<div data-lang="ko"><p><b>Set A</b>＝6패턴 계열 / <b>Set B</b>＝10패턴 계열. <b>둘 중 하나</b> 선택. 지시가 없으면 관리자에게 확인.</p></div>

<h3><span class="lbl">Reverse</span> / <span class="lbl">Safety mode</span><span data-lang="ja">逆張り / セーフティ</span><span data-lang="ko">역배팅 / 세이프티</span></h3>
<div data-lang="ja"><p><b>Reverse</b>：初心者は <b>OFF</b>。エッジはありません（規律用）。再起動で必ずOFFに戻ります。<br><b>Safety mode</b>：初心者は <b>OFF</b>（常時BET）。</p></div>
<div data-lang="ko"><p><b>Reverse</b>: 초보자는 <b>OFF</b>. 우위는 없습니다（규율용）. 재실행 시 반드시 OFF로 돌아감.<br><b>Safety mode</b>: 초보자는 <b>OFF</b>（상시 BET）.</p></div>

<h3><span class="lbl">MONEY MODE</span><span data-lang="ja">資金管理モード（一番大事）</span><span data-lang="ko">자금관리 모드（가장 중요）</span></h3>
<div data-lang="ja"><table><tr><th>画面表示</th><th>意味</th><th>向き</th></tr>
<tr><td>SEQ (small SEQ)</td><td>階段状に賭金を上げる主力</td><td><span class="tag ok">✅ 基本</span></td></tr>
<tr><td>Proportional (Kelly)</td><td>残高に比例（複利・破滅しない）</td><td>中級</td></tr>
<tr><td>1-2-3 x set</td><td>7手ごと 1→2→3（破滅しない）</td><td>安全</td></tr>
<tr><td>D'Alembert x set</td><td>7手ごと ±1ユニット（要ロスカット）</td><td>中級</td></tr>
<tr><td>Fibonacci grid</td><td>2次元グリッドで利確/損切選択</td><td>上級</td></tr>
<tr><td>Flat / Martingale / D'Alembert</td><td>固定 / 倍がけ / ダランベール</td><td>用途別</td></tr></table><p>初心者は <b>SEQ (small SEQ)</b>。</p></div>
<div data-lang="ko"><table><tr><th>화면 표시</th><th>의미</th><th>대상</th></tr>
<tr><td>SEQ (small SEQ)</td><td>계단식으로 베팅액을 올리는 주력</td><td><span class="tag ok">✅ 기본</span></td></tr>
<tr><td>Proportional (Kelly)</td><td>잔고에 비례（복리·파산 안 함）</td><td>중급</td></tr>
<tr><td>1-2-3 x set</td><td>7수마다 1→2→3（파산 안 함）</td><td>안전</td></tr>
<tr><td>D'Alembert x set</td><td>7수마다 ±1유닛（손절 필요）</td><td>중급</td></tr>
<tr><td>Fibonacci grid</td><td>2차원 그리드로 익절/손절 선택</td><td>상급</td></tr>
<tr><td>Flat / Martingale / D'Alembert</td><td>고정 / 마틴게일 / 달랑베르</td><td>용도별</td></tr></table><p>초보자는 <b>SEQ (small SEQ)</b>.</p></div>

<h3><span class="lbl">SEQ type</span> / <span class="lbl">Start amount</span> / <span class="lbl">Shape</span><span data-lang="ja">SEQの設定</span><span data-lang="ko">SEQ 설정</span></h3>
<div data-lang="ja">
  <p><b>SEQ type</b>：<b>Small SEQ (28 steps)</b>推奨 / Classic SEQ (48 steps)。<br><b>Start amount</b>：SEQ階段の1段目の額（$0.2刻み）。</p>
  <div class="callout warn"><span class="ic">⚠️</span> 開始額は<b>元本の0.3〜0.5%</b>が目安（例：元本$49→$0.20）。</div>
  <table><tr><th>Shape</th><th>特徴</th></tr>
  <tr><td>Attack</td><td>攻撃型：利益最大・飛びやすい</td></tr>
  <tr><td>Balance</td><td>中間（利益77%）</td></tr>
  <tr><td>Defense</td><td>守備型：<b>最も飛びにくい</b>（利益56%）</td></tr></table>
  <div class="callout warn"><span class="ic">⚠️</span> <b>少額元本なら Defense（守備型）を強く推奨。</b>攻撃型は少額だと危険。</div>
</div>
<div data-lang="ko">
  <p><b>SEQ type</b>: <b>Small SEQ (28 steps)</b> 권장 / Classic SEQ (48 steps).<br><b>Start amount</b>: SEQ 사다리 1단계 금액（$0.2 단위）.</p>
  <div class="callout warn"><span class="ic">⚠️</span> 시작 금액은 <b>원금의 0.3〜0.5%</b>가 기준（예: 원금 $49→$0.20）.</div>
  <table><tr><th>Shape</th><th>특징</th></tr>
  <tr><td>Attack</td><td>공격형: 이익 최대·터지기 쉬움</td></tr>
  <tr><td>Balance</td><td>중간（이익 77%）</td></tr>
  <tr><td>Defense</td><td>수비형: <b>가장 안 터짐</b>（이익 56%）</td></tr></table>
  <div class="callout warn"><span class="ic">⚠️</span> <b>소액 원금이면 Defense（수비형） 강력 권장.</b>공격형은 소액에서 위험.</div>
</div>

<h3><span class="lbl">Take profit</span> / <span class="lbl">Loss cut</span><span data-lang="ja">利確 / 損切り</span><span data-lang="ko">익절 / 손절</span></h3>
<div data-lang="ja">
  <p><b>Take profit</b>：この利益額で自動停止（0=無効）。<br><b>Loss cut</b>：この損失額で自動停止（全モード共通）0=無効。</p>
  <div class="callout warn"><span class="ic">⚠️</span> <b>少額元本では Loss cut を必ず設定。</b>目安＝元本の40〜50%（例：元本$49なら $20〜$25）。</div>
</div>
<div data-lang="ko">
  <p><b>Take profit</b>: 이 이익 금액에서 자동 정지（0=무효）.<br><b>Loss cut</b>: 이 손실 금액에서 자동 정지（전 모드 공통）0=무효.</p>
  <div class="callout warn"><span class="ic">⚠️</span> <b>소액 원금이면 Loss cut을 반드시 설정.</b>기준＝원금의 40〜50%（예: 원금 $49면 $20〜$25）.</div>
</div>

<div class="card" data-lang="ja"><b style="color:#5cdfff">設定が終わったら</b><ol><li><b>SAVE</b>（サーバーへ送信）。</li><li><b>START</b> を押す。</li><li>Stakeが<b>マルチエリア表示</b>か確認。</li><li>上部が <b class="tag ok">ONLINE</b> → しばらくで<b>黄色枠</b>が付きBETが入る。</li></ol><div class="callout tip"><span class="ic">💡</span> 設定を変えたら<b>必ずSAVE</b>。</div></div>
<div class="card" data-lang="ko"><b style="color:#5cdfff">설정이 끝나면</b><ol><li><b>SAVE</b>（서버로 전송）.</li><li><b>START</b> 를 누릅니다.</li><li>Stake가 <b>멀티에어리어 표시</b>인지 확인.</li><li>상단이 <b class="tag ok">ONLINE</b> → 잠시 후 <b>노란 테두리</b>가 붙고 BET이 들어옴.</li></ol><div class="callout tip"><span class="ic">💡</span> 설정을 바꾸면 <b>반드시 SAVE</b>.</div></div>

<h2><span class="num">⑤</span><span data-lang="ja">不具合集（症状と対処）</span><span data-lang="ko">문제 해결（증상과 대처）</span></h2>

<h3><span data-lang="ja">1. BETしない</span><span data-lang="ko">1. BET이 안 됨</span></h3>
<div data-lang="ja"><ol><li><b>START・SAVEを押したか？</b></li><li>上部が <b class="tag ok">ONLINE</b> か？<code>OFFLINE</code>なら<b>GUI再起動</b>。</li><li>Stakeに<b>ログイン済</b>か？<b>マルチエリア表示</b>か？</li><li><b>まだ高確度の信号が来ていないだけ</b>かも（BETは強い信号時のみ・数分に1回程度）。</li><li>全台「ログインしていない」＝Stake障害 → <b>GUI再起動</b>で回復。</li></ol></div>
<div data-lang="ko"><ol><li><b>START·SAVE를 눌렀는가?</b></li><li>상단이 <b class="tag ok">ONLINE</b> 인가? <code>OFFLINE</code>이면 <b>GUI 재실행</b>.</li><li>Stake에 <b>로그인</b> 되었는가? <b>멀티에어리어 표시</b>인가?</li><li><b>아직 고확률 신호가 오지 않았을 뿐</b>일 수있음（BET은 강한 신호일 때만·몇 분에 1회）.</li><li>전 테이블 「로그인 안 됨」＝Stake 장애 → <b>GUI 재실행</b>으로 회복.</li></ol></div>

<h3><span data-lang="ja">2. 黄色枠がつかない</span><span data-lang="ko">2. 노란 테두리가 안 붙음</span></h3>
<div data-lang="ja"><ol><li><b>マルチエリア画面に手動で入っているか？</b>（最多の原因）</li><li>上部が <b class="tag ok">ONLINE</b> か？<code>OFFLINE</code>／<code>matar OFFLINE</code>なら<b>GUI再起動</b>。</li><li>Signal set（A/B）が運用の系統と合っているか。</li><li>しばらく信号が無いだけ（正常）。数分待つ。</li></ol></div>
<div data-lang="ko"><ol><li><b>멀티에어리어 화면에 수동으로 들어갔는가?</b>（가장 많은 원인）</li><li>상단이 <b class="tag ok">ONLINE</b> 인가? <code>OFFLINE</code>／<code>matar OFFLINE</code>이면 <b>GUI 재실행</b>.</li><li>Signal set（A/B）가 운영 계열과 맞는가.</li><li>잠시 신호가 없을 뿐（정상）. 몇 분 기다림.</li></ol></div>

<h3><span data-lang="ja">3. 黄色枠が長く光る</span><span data-lang="ko">3. 노란 테두리가 오래 켜짐</span></h3>
<div data-lang="ja"><p>黄色枠は「<b>1歩手前の予告</b>」。本番信号（NOW）を待つ状態なので光り続けるのは<b>正常</b>です。異常に長い場合：卓の停滞／シューチェンジ待ち → 別卓が正常なら問題なし。全卓で光りっぱなしなら<b>GUI再起動</b>。</p></div>
<div data-lang="ko"><p>노란 테두리는 「<b>한 발 앞선 예고</b>」. 실제 신호（NOW）를 기다리는 상태라 계속 켜지는 것은 <b>정상</b>입니다. 비정상적으로 길 때: 테이블 정체／슈 체인지 대기 → 다른 테이블이 정상이면 문제없음. 전 테이블에서 계속 켜진 채 멈추면 <b>GUI 재실행</b>.</p></div>

<h3><span data-lang="ja">4. エラー・その他</span><span data-lang="ko">4. 오류·기타</span></h3>
<div data-lang="ja"><table><tr><th>症状</th><th>対処</th></tr>
<tr><td>"Failed to start third party session"</td><td>ライブバカラの<b>正規ページから</b>入り直す</td></tr>
<tr><td>Chromeが自動で立ち上がらない</td><td><b>GUI再起動</b></td></tr>
<tr><td>Stakeがログアウト</td><td>自動Chromeで<b>再ログイン</b></td></tr>
<tr><td>急に動かない／エンジン死亡</td><td>まず<b>GUI再起動</b></td></tr>
<tr><td>チャートが「蓄積中」</td><td>正常。連続稼働で自動表示</td></tr></table></div>
<div data-lang="ko"><table><tr><th>증상</th><th>대처</th></tr>
<tr><td>"Failed to start third party session"</td><td>라이브 바카라 <b>정식 페이지에서</b> 다시 진입</td></tr>
<tr><td>Chrome이 자동 실행 안 됨</td><td><b>GUI 재실행</b></td></tr>
<tr><td>Stake 로그아웃됨</td><td>자동 Chrome에서 <b>재로그인</b></td></tr>
<tr><td>갑자기 멈춤／엔진 사망</td><td>우선 <b>GUI 재실행</b></td></tr>
<tr><td>차트가 「축적 중」</td><td>정상. 연속 가동으로 자동 표시</td></tr></table></div>

<div class="callout tip" data-lang="ja"><span class="ic">📊</span> <b>勝率チャート</b>：<b>サーバー側で24時間計測</b>しており、GUIを閉じても止まりません。<b>bot再起動でも数字はリセットされず続き</b>から貯まります。</div>
<div class="callout tip" data-lang="ko"><span class="ic">📊</span> <b>승률 차트</b>: <b>서버에서 24시간 측정</b>하며 GUI를 닫아도 멈추지 않습니다. <b>bot 재실행에도 숫자는 초기화되지 않고 이어서</b> 쌓입니다.</div>

<h2><span data-lang="ja">困ったら まず「GUI再起動」</span><span data-lang="ko">문제가 생기면 우선 「GUI 재실행」</span></h2>
<div class="card" data-lang="ja"><p>多くの不具合（OFFLINE・黄色枠が出ない・BETしない・エンジン死亡）は、<b>GUIを閉じて開き直す</b>だけで回復します。それでも直らない時は <b>管理者にリモートサポート（SSH）を依頼</b>。</p></div>
<div class="card" data-lang="ko"><p>대부분의 문제（OFFLINE·노란 테두리 안 나옴·BET 안 됨·엔진 사망）는 <b>GUI를 닫았다 다시 여는</b> 것만으로 회복됩니다. 그래도 안 되면 <b>관리자에게 원격 지원（SSH） 요청</b>.</p></div>

<h2><span data-lang="ja">稼働チェックリスト</span><span data-lang="ko">가동 체크리스트</span></h2>
<ul class="checklist" data-lang="ja"><li>bafather.uk にログインできた</li><li>自動Chromeで Stake にログイン済</li><li>Stakeが<b>マルチエリア表示</b></li><li>設定を確認して <b>SAVE</b></li><li><b>START</b> を押した</li><li>上部が <b class="tag ok">ONLINE</b></li><li>しばらくで<b>黄色枠</b>が付きBETが入る</li></ul>
<ul class="checklist" data-lang="ko"><li>bafather.uk 로그인 성공</li><li>자동 Chrome에서 Stake 로그인 완료</li><li>Stake가 <b>멀티에어리어 표시</b></li><li>설정 확인 후 <b>SAVE</b></li><li><b>START</b> 누름</li><li>상단이 <b class="tag ok">ONLINE</b></li><li>잠시 후 <b>노란 테두리</b>가 붙고 BET 들어옴</li></ul>

<div class="m-footer" data-lang="ja">KBKOREA 利用マニュアル · bafather · 本ページは会員向けの操作説明です</div>
<div class="m-footer" data-lang="ko">KBKOREA 이용 매뉴얼 · bafather · 본 페이지는 회원용 조작 안내입니다</div>
`

export default function ManualPage() {
  const [lang, setLang] = useState<'ja' | 'ko'>('ja')

  useEffect(() => {
    try {
      const saved = localStorage.getItem('kbkorea_manual_lang')
      if (saved === 'ko' || saved === 'ja') setLang(saved)
    } catch { /* ignore */ }
  }, [])

  function pick(l: 'ja' | 'ko') {
    setLang(l)
    try { localStorage.setItem('kbkorea_manual_lang', l) } catch { /* ignore */ }
  }

  const btn = (l: 'ja' | 'ko', label: string) => (
    <button
      onClick={() => pick(l)}
      className={`rounded-full border px-4 py-1.5 text-[13px] font-semibold transition ${
        lang === l
          ? 'border-cyan bg-cyan text-[#04121a]'
          : 'border-border bg-surface-2 text-text-muted hover:text-text'
      }`}
    >
      {label}
    </button>
  )

  return (
    <div>
      <PageHeader
        kicker="Member · Manual"
        title={lang === 'ja' ? '利用マニュアル' : '이용 매뉴얼'}
        sub={lang === 'ja' ? 'KBKOREA GUI の使い方（初心者向け）' : 'KBKOREA GUI 사용법 (초보자용)'}
        right={<div className="flex gap-1.5">{btn('ja', '日本語')}{btn('ko', '한국어')}</div>}
      />
      <style dangerouslySetInnerHTML={{ __html: MANUAL_CSS }} />
      <div
        className={`manual-root lang-${lang}`}
        dangerouslySetInnerHTML={{ __html: MANUAL_BODY }}
      />
    </div>
  )
}
