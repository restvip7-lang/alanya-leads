/**
 * Google Таблица «Заявки Алания» для Асель.
 * Парсер присылает сюда новые заявки (внизу списка), Асель ставит статус и пишет комментарий.
 *
 * Установка (один раз): см. google_sheet/README.md
 *   1. Расширения → Apps Script, вставить этот файл, в SECRET вписать свой пароль.
 *   2. Запустить функцию setup (создаст лист, колонки, выпадающий список статусов, цвета).
 *   3. Начать развёртывание → Веб-приложение, «Выполнять от моего имени», доступ «Все».
 *   4. Ссылку /exec вписать в config.ini парсера как webhook_url, пароль как webhook_secret.
 */

const SECRET = 'ПОМЕНЯЙТЕ-МЕНЯ';
const SHEET = 'Заявки';

const STATUSES = ['Новая', 'Не дозвонилась', 'Написала', 'В работе', 'Показ назначен', 'Сделка', 'Не актуально'];
const STATUS_COLORS = {
  'Новая': '#fff2cc', 'Не дозвонилась': '#fce5cd', 'Написала': '#cfe2f3', 'В работе': '#c9daf8',
  'Показ назначен': '#d9d2e9', 'Сделка': '#b6d7a8', 'Не актуально': '#e0e0e0',
};

// Колонки Асель + поля заявки из парсера (ключ из JSON → заголовок)
const COLUMNS = [
  ['status', 'Статус'], ['comment', 'Комментарий'], ['next', 'Следующий шаг (дата)'],
  ['date', 'Дата заявки'], ['source', 'Источник'], ['chat', 'Чат / группа'], ['author', 'Автор'],
  ['author_profile', 'Профиль'], ['contacts', 'Контакты в тексте'], ['budget', 'Бюджет'],
  ['currency', 'Валюта'], ['property_type', 'Тип'], ['districts', 'Район'], ['text', 'Текст'],
  ['link', 'Ссылка'], ['id', '_id'],
];
const COL = Object.fromEntries(COLUMNS.map(([k], i) => [k, i + 1]));

function sheet_() {
  const ss = SpreadsheetApp.getActive();
  return ss.getSheetByName(SHEET) || ss.insertSheet(SHEET);
}

function setup() {
  const sh = sheet_();
  sh.getRange(1, 1, 1, COLUMNS.length).setValues([COLUMNS.map(c => c[1])])
    .setFontWeight('bold').setBackground('#f3f3f3');
  sh.setFrozenRows(1);
  sh.setFrozenColumns(2);
  const widths = { status: 140, comment: 260, next: 120, date: 120, chat: 160, text: 420, link: 90, id: 40 };
  for (const [k, w] of Object.entries(widths)) sh.setColumnWidth(COL[k], w);
  sh.hideColumns(COL.id);
  sh.getRange(2, COL.text, sh.getMaxRows() - 1, 1).setWrap(true).setVerticalAlignment('top');

  const rows = sh.getMaxRows() - 1;
  sh.getRange(2, COL.status, rows, 1).setDataValidation(statusRule_());
  sh.getRange(2, COL.next, rows, 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireDate().setAllowInvalid(true).build()).setNumberFormat('dd.mm.yyyy');

  // Цвет всей строки по статусу
  const whole = sh.getRange(2, 1, rows, COLUMNS.length);
  const L = String.fromCharCode(64 + COL.status);
  sh.setConditionalFormatRules(Object.entries(STATUS_COLORS).map(([s, color]) =>
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied(`=$${L}2="${s}"`)
      .setBackground(color).setRanges([whole]).build()));

  if (!sh.getFilter()) sh.getRange(1, 1, sh.getMaxRows(), COLUMNS.length).createFilter();
}

function statusRule_() {
  return SpreadsheetApp.newDataValidation().requireValueInList(STATUSES, true).setAllowInvalid(false).build();
}

function doPost(e) {
  let lead;
  try { lead = JSON.parse(e.postData.contents); } catch (err) { return json_({ ok: false, error: 'bad json' }); }
  if (lead.secret !== SECRET) return json_({ ok: false, error: 'forbidden' });
  if (!lead.id) return json_({ ok: false, error: 'no id' });

  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const sh = sheet_();
    const last = sh.getLastRow();
    if (last > 1) {
      const ids = sh.getRange(2, COL.id, last - 1, 1).getValues().flat();
      if (ids.includes(lead.id)) return json_({ ok: true, duplicate: true });
    }
    const row = COLUMNS.map(([k]) => {
      if (k === 'status') return 'Новая';
      if (k === 'comment' || k === 'next') return '';
      if (k === 'link') return '';
      const v = lead[k] == null ? '' : lead[k];
      // Текст из чатов не должен выполняться как формула
      return typeof v === 'string' && /^[=+\-@]/.test(v) ? "'" + v : v;
    });
    const r = sh.getLastRow() + 1;
    sh.getRange(r, 1, 1, row.length).setValues([row]);
    sh.getRange(r, COL.status).setDataValidation(statusRule_());
    sh.getRange(r, COL.next).setNumberFormat('dd.mm.yyyy');
    sh.getRange(r, COL.text).setWrap(true).setVerticalAlignment('top');
    if (/^https?:\/\//.test(lead.link || '')) {
      sh.getRange(r, COL.link).setRichTextValue(
        SpreadsheetApp.newRichTextValue().setText('открыть').setLinkUrl(lead.link).build());
    }
    return json_({ ok: true });
  } finally {
    lock.releaseLock();
  }
}

function doGet() {
  return json_({ ok: true, info: 'Заявки Алания: приём работает' });
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
