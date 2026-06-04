# Quotes MVP — локальное тестирование

Сюда кладём GIF-ки / картинки / варианты разметки и смотрим через **grip** как будет выглядеть на GitHub.

Когда нужный вариант найден — переносим в основной `README.md` репозитория.

---

## Тест 1: GIF справа с плавающим положением

<img align="right" width="420" src="./sample.gif" alt="Sample" />

<details>
  <summary>About me</summary>
  <br/>

Здесь обычный контент About me. Когда картинка справа плавает, текст обтекает её слева.

</details>

<details>
  <summary>Projects</summary>
  <br/>

Второй свёрнутый блок.

</details>

---

## Тест 2: Статичная картинка с подписью

<p align="center">
  <img src="./sample.gif" width="480" alt="Sample" />
</p>
<p align="center"><em>"Nil Satis Nisi Optimum"</em></p>

---

## Тест 3: Таблица 2 колонки (картинка + текст)

<table>
<tr>
<td width="50%">
  <img src="./sample.gif" width="100%" alt="Sample" />
</td>
<td width="50%" valign="top">

### Заголовок справа

Можно класть сюда markdown текст, он рендерится.

- Элемент 1
- Элемент 2

</td>
</tr>
</table>
