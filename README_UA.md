# Home Assistant: Інтеграція ConnectHome Butler

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA](https://img.shields.io/badge/Home%20Assistant-2024.1+-18BCF2?logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)

<p align="center">
  <img src="icon.png" alt="ConnectHome" width="200">
  &nbsp;&nbsp;&nbsp;
  <img src="https://brands.home-assistant.io/_/homeassistant/logo.png" alt="Home Assistant" width="100">
</p>

> **Відмова від відповідальності**: Це неофіційна інтеграція, створена ентузіастом. Вона не пов'язана з компаніями ConnectHome або Home Assistant і не підтримується ними. Використовуйте на власний ризик. Автор не несе відповідальності за будь-які збитки, втрату даних чи інші проблеми, спричинені використанням цієї інтеграції.

Кастомна інтеграція для Home Assistant, що підключається до контролера розумного будинку [ConnectHome Butler](https://c-home.ua/).

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

MIT
