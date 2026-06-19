// === БИОЛОГИЧЕСКИЙ ВОЗРАСТ ===

const bioQuestions = [
  { q: "Качество сна", opts: ["Сплю отлично (−2)", "Бывают проблемы (0)", "Плохо сплю (+3)"], scores: [-2, 0, 3] },
  { q: "Артериальное давление", opts: ["В норме (−1)", "Незначительно повышено (+2)", "Высокое или на таблетках (+5)"], scores: [-1, 2, 5] },
  { q: "Физическая активность", opts: ["Спорт 3+ раз в неделю (−3)", "Лёгкие прогулки (0)", "Практически не двигаюсь (+4)"], scores: [-3, 0, 4] },
  { q: "Питание", opts: ["Разнообразное, без фастфуда (−2)", "Иногда нездорово (0)", "Фастфуд, мало овощей (+3)"], scores: [-2, 0, 3] },
  { q: "Вес", opts: ["Нормальный ИМТ (−1)", "Лёгкий лишний вес (+2)", "Ожирение (+5)"], scores: [-1, 2, 5] },
  { q: "Курение", opts: ["Не курю (−1)", "Курил раньше (+1)", "Курю (+4)"], scores: [-1, 1, 4] },
  { q: "Алкоголь", opts: ["Не пью или редко (−1)", "1–2 раза в неделю (+2)", "Часто (+5)"], scores: [-1, 2, 5] },
  { q: "Энергия в течение дня", opts: ["Бодрость весь день (−2)", "Бывает усталость (+1)", "Постоянная усталость (+4)"], scores: [-2, 1, 4] },
  { q: "Гибкость и подвижность суставов", opts: ["Хорошая (−1)", "Небольшая скованность (+1)", "Суставы болят (+3)"], scores: [-1, 1, 3] },
  { q: "Память и концентрация", opts: ["Острая (−2)", "Иногда забываю (+1)", "Частые провалы памяти (+3)"], scores: [-2, 1, 3] },
  { q: "Кожа", opts: ["Упругая, без морщин (−1)", "Умеренные изменения (+1)", "Много морщин, дряблость (+3)"], scores: [-1, 1, 3] },
  { q: "Стресс", opts: ["Спокоен, управляю стрессом (−1)", "Умеренный стресс (+1)", "Постоянный стресс (+4)"], scores: [-1, 1, 4] },
  { q: "Хронические заболевания", opts: ["Нет (−2)", "Одно контролируемое (+2)", "Несколько или неконтролируемые (+5)"], scores: [-2, 2, 5] },
  { q: "Рацион питания — овощи и фрукты", opts: ["5+ порций ежедневно (−2)", "2–4 порции (0)", "Редко ем овощи (+2)"], scores: [-2, 0, 2] },
  { q: "Регулярность медосмотров", opts: ["Раз в год и чаще (−1)", "Когда что-то болит (+1)", "Не хожу к врачам (+2)"], scores: [-1, 1, 2] },
];

function renderBioAgeQuestions() {
  const container = document.getElementById('bioage-questions');
  container.innerHTML = bioQuestions.map((q, i) => `
    <div class="bioage-q">
      <p>${i + 1}. ${q.q}</p>
      <div class="options">
        ${q.opts.map((opt, j) => `
          <label>
            <input type="radio" name="ba${i}" value="${q.scores[j]}" />
            ${opt}
          </label>
        `).join('')}
      </div>
    </div>
  `).join('');
}

function calcBioAge() {
  const resultEl = document.getElementById('bioage-result');
  let total = 0;
  let answered = 0;

  for (let i = 0; i < bioQuestions.length; i++) {
    const sel = document.querySelector(`input[name="ba${i}"]:checked`);
    if (sel) { total += parseInt(sel.value); answered++; }
  }

  if (answered < bioQuestions.length) {
    resultEl.innerHTML = `<p style="color:#c0392b">Пожалуйста, ответьте на все ${bioQuestions.length} вопросов.</p>`;
    resultEl.classList.remove('hidden');
    return;
  }

  const passport = parseInt(document.getElementById('kbju-age')?.value) || 40;
  // Базовый биовозраст: паспортный возраст + поправка на сумму баллов
  // Нейтраль = 0 баллов, диапазон примерно от -18 до +52
  const bio = passport + Math.round(total / 3.5);

  let comment = '';
  const diff = bio - passport;
  if (diff <= -3) comment = 'Отлично! Ваш организм моложе паспортного возраста.';
  else if (diff <= 3) comment = 'Хорошо. Биологический возраст соответствует паспортному.';
  else if (diff <= 8) comment = 'Есть резервы для улучшения. Скорректируйте питание и активность.';
  else comment = 'Организм стареет быстрее нормы. Рекомендуется консультация специалиста.';

  resultEl.innerHTML = `
    <h3>Ваш биологический возраст</h3>
    <div class="big-num">${bio} лет</div>
    <p style="margin-top:10px">${comment}</p>
    <p style="margin-top:14px;font-size:0.9rem;color:#666">Хотите узнать как питание влияет на ваш биологический возраст?
    <a href="#contact" style="color:#4a7c59;font-weight:600">Запишитесь на консультацию →</a></p>
  `;
  resultEl.classList.remove('hidden');
}

// === КАЛЬКУЛЯТОР КБЖУ ===

function calcKBJU() {
  const sex = document.getElementById('kbju-sex').value;
  const age = parseFloat(document.getElementById('kbju-age').value);
  const h = parseFloat(document.getElementById('kbju-height').value);
  const w = parseFloat(document.getElementById('kbju-weight').value);
  const act = parseFloat(document.getElementById('kbju-activity').value);
  const goal = parseFloat(document.getElementById('kbju-goal').value);
  const res = document.getElementById('kbju-result');

  if (!age || !h || !w) {
    res.innerHTML = '<p style="color:#c0392b">Заполните все поля.</p>';
    res.classList.remove('hidden');
    return;
  }

  // Формула Миффлина-Сан Жеора
  let bmr;
  if (sex === 'f') bmr = 9.99 * w + 6.25 * h - 4.92 * age - 161;
  else bmr = 9.99 * w + 6.25 * h - 4.92 * age + 5;

  const tdee = Math.round(bmr * act * goal);
  const protein = Math.round(w * 1.6);
  const fat = Math.round(tdee * 0.28 / 9);
  const carbs = Math.round((tdee - protein * 4 - fat * 9) / 4);

  res.innerHTML = `
    <h3>Ваша суточная норма</h3>
    <div class="big-num">${tdee} ккал</div>
    <ul style="margin-top:12px">
      <li><b>Белки:</b> ${protein} г</li>
      <li><b>Жиры:</b> ${fat} г</li>
      <li><b>Углеводы:</b> ${carbs} г</li>
    </ul>
    <p style="margin-top:14px;font-size:0.9rem;color:#666">Хотите точный план питания под ваши цели?
    <a href="#contact" style="color:#4a7c59;font-weight:600">Записаться к Маргарите →</a></p>
  `;
  res.classList.remove('hidden');
}

// === НЕЖЕЛАТЕЛЬНЫЕ ПРОДУКТЫ ===

const productRules = {
  'p-lactose': {
    label: 'Лактозная непереносимость',
    products: ['Цельное молоко', 'Сливочное масло (в большом кол-ве)', 'Мороженое', 'Сливки', 'Мягкие свежие сыры (рикотта, маскарпоне)'],
  },
  'p-gluten': {
    label: 'Возможная глютеновая чувствительность',
    products: ['Пшеничный хлеб', 'Макароны из пшеницы', 'Манка', 'Булгур', 'Перловка', 'Большинство готовых соусов (скрытый глютен)'],
  },
  'p-sugar': {
    label: 'Повышенный сахар / диабет 2 типа',
    products: ['Белый сахар', 'Мёд (в большом кол-ве)', 'Белый рис', 'Картофель (варёный/пюре)', 'Сладкие соки и газировка', 'Белый хлеб', 'Финики, бананы (в избытке)'],
  },
  'p-gkt': {
    label: 'Гастрит / изжога / рефлюкс',
    products: ['Кофе и крепкий чай', 'Острые специи', 'Цитрусовые натощак', 'Жирное жареное', 'Алкоголь', 'Газированные напитки', 'Помидоры и томатный соус'],
  },
  'p-thyroid': {
    label: 'Щитовидная железа',
    products: ['Сырая капуста (в большом кол-ве)', 'Сырая брюква и репа', 'Необработанное просо', 'Избыток сои', 'Избыток йодированной соли (при гипертиреозе)'],
  },
  'p-heart': {
    label: 'Сердце и давление',
    products: ['Солёное (чипсы, соленья, консервы)', 'Трансжиры (маргарин, фастфуд)', 'Колбасные изделия', 'Субпродукты', 'Крепкий кофе (при гипертонии)'],
  },
  'p-kidney': {
    label: 'Почки / мочекаменная болезнь',
    products: ['Шпинат и щавель (оксалаты)', 'Шоколад', 'Орехи (в большом кол-ве)', 'Бобовые (при уратном диурезе)', 'Пуриновые продукты: субпродукты, анчоусы'],
  },
  'p-allergy': {
    label: 'Пищевая аллергия',
    products: ['Орехи (арахис, кешью, грецкий)', 'Яйца и блюда с яйцами', 'Рыба и морепродукты', 'Скрытые аллергены в соусах и полуфабрикатах'],
  },
};

function calcProducts() {
  const res = document.getElementById('products-result');
  const checked = Object.keys(productRules).filter(id => document.getElementById(id)?.checked);

  if (checked.length === 0) {
    res.innerHTML = '<p style="color:#2d5a3d;font-weight:500">Вы отметили, что особых ограничений нет. Это хорошо!</p>';
    res.classList.remove('hidden');
    return;
  }

  let html = '<h3>Нежелательные продукты для вас:</h3>';
  checked.forEach(id => {
    const rule = productRules[id];
    html += `<p style="margin-top:12px"><b>${rule.label}:</b></p><ul>` +
      rule.products.map(p => `<li>${p}</li>`).join('') + '</ul>';
  });
  html += `<p style="margin-top:16px;font-size:0.9rem;color:#666">Это общие рекомендации. Для точного плана питания с учётом ваших анализов —
    <a href="#contact" style="color:#4a7c59;font-weight:600">запишитесь к Маргарите →</a></p>`;

  res.innerHTML = html;
  res.classList.remove('hidden');
}

// INIT
document.addEventListener('DOMContentLoaded', renderBioAgeQuestions);
