<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/connecthome/brand/dark_logo@2x.png">
    <source media="(prefers-color-scheme: light)" srcset="custom_components/connecthome/brand/logo@2x.png">
    <img src="custom_components/connecthome/brand/logo@2x.png" alt="ConnectHome" width="280">
  </picture>
</p>

<h1 align="center">ConnectHome Butler</h1>

<p align="center">
  Підключіть <a href="https://c-home.ua/">контролер розумного будинку Butler</a> до <a href="https://www.home-assistant.io/">Home Assistant</a>.<br>
  Локальне керування &nbsp;·&nbsp; Оновлення в реальному часі &nbsp;·&nbsp; Автоматичний пошук
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-orange?style=flat-square" alt="Кастомна інтеграція HACS"></a>
  <a href="https://www.home-assistant.io/"><img src="https://img.shields.io/badge/Home%20Assistant-2024.1%2B-18BCF2?style=flat-square&amp;logo=home-assistant&amp;logoColor=white" alt="Home Assistant 2024.1 або новіший"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-3d5ba7?style=flat-square" alt="Ліцензія MIT"></a>
</p>

<p align="center">
  <a href="README.md">English</a> &nbsp;·&nbsp; <strong>Українська</strong><br>
  <a href="#встановлення">Встановлення</a> &nbsp;·&nbsp; <a href="#підтримувані-пристрої">Підтримувані пристрої</a> &nbsp;·&nbsp; <a href="https://github.com/BODYA7979/ha-connecthome/issues">Повідомити про проблему</a>
</p>

<details>
<summary>Неофіційна інтеграція — відмова від відповідальності</summary>

Це неофіційна інтеграція, створена ентузіастом. Вона не пов'язана з компаніями ConnectHome або Home Assistant і не підтримується ними. Використовуйте на власний ризик. Автор не несе відповідальності за будь-які збитки, втрату даних чи інші проблеми, спричинені використанням цієї інтеграції.

</details>

## Можливості

- **Усі типи пристроїв**: вимикачі, димери, RGB-світло, ролети, термостати, замки, датчики температури/вологості/освітленості, датчики руху/дверей/вікон/диму/протікання
- **Оновлення в реальному часі**: long-polling через Butler API, зміни стану з'являються менш ніж за секунду
- **Автоматичний пошук**: UDP-виявлення контролерів Butler у локальній мережі
- **Прив'язка до кімнат**: назви пристроїв містять назву кімнати (напр. "Вимикач світла (Кухня)")
- **Живі зміни**: перейменування/додавання/видалення пристроїв у додатку Butler автоматично підхоплюються в HA

## Встановлення

### Через HACS (рекомендовано)

1. Відкрийте HACS у Home Assistant
2. Перейдіть до **Integrations** → ⋮ → **Custom repositories**
3. Вставте `https://github.com/BODYA7979/ha-connecthome` → Категорія: **Integration**
4. Натисніть **Download**
5. Перезавантажте Home Assistant

### Вручну

```bash
cd /config/custom_components
git clone https://github.com/BODYA7979/ha-connecthome.git connecthome
# Перезавантажте Home Assistant
```

## Налаштування

1. Settings → Devices & Services → Add Integration
2. Знайдіть **ConnectHome Butler**
3. Введіть IP контролера Butler, логін і пароль
4. Якщо контролери знайдено автоматично, вони будуть показані на екрані налаштування

## Підтримувані пристрої

| Butler Device Type | Home Assistant Entity |
|---|---|
| DevSwitch | `switch` |
| DevDimmer | `light` (яскравість) |
| DevDimmerColor | `light` (RGBW) |
| DevShutter | `cover` (ролети, позиція) |
| DevBinarySensor | `binary_sensor` (рух, двері, вікно, дим, протікання) |
| DevTemperature | `sensor` (температура) |
| DevHygrometry | `sensor` (вологість) |
| DevLuminosity | `sensor` (освітленість) |
| DevGenericSensor | `sensor` |
| DevThermostat | `climate` (режим, цільова температура, стан) |
| DevDoorLock | `lock` |
| DevMeter | `sensor` (потужність) |

## Вимоги

- Home Assistant 2024.1.0+
- Контролер ConnectHome Butler з прошивкою 0.9+
- Для іконок і логотипів інтеграції в інтерфейсі Home Assistant потрібна версія 2026.3+.

## Відомі обмеження

Не всі типи пристроїв протестовані на реальному обладнанні, оскільки автор не володіє кожним типом пристроїв, сумісних з Butler. Якщо щось не працює — будь ласка, [створіть Issue](https://github.com/BODYA7979/ha-connecthome/issues), а ще краще — надішліть Pull Request з виправленням.

## Розробка

```bash
# Перевірка синтаксису
for f in custom_components/connecthome/*.py; do python3 -c "import ast; ast.parse(open('$f').read())" && echo "OK $f"; done

# Увімкнути дебаг-логування (в configuration.yaml)
logger:
  logs:
    custom_components.connecthome: debug
```

## Ліцензія

[MIT](LICENSE)
