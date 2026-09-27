# MVP 0.3 acceptance test

Основной тест выполняется только на отдельном тестовом Windows-ПК или VM. До начала
нужно проверить `Emergency-Recovery.cmd` и иметь доступ к локальной консоли, не
зависящий от сети.

## Подготовка

1. Несколько циклов запустить Core в режиме `Shadow`.
2. Заполнить `vpnConnectionName` либо `vpnReconnectCommand`.
3. Для реального Fail-Closed заполнить `vpnServerIps`; без whitelist Core обязан
   отказаться удалять default route.
4. Убедиться, что Direct IP и VPN IP появились в `data/core-state.json`.
5. Проверить `Run-SelfTest.cmd` и `Emergency-Recovery.cmd`.

## Один цикл

1. Начальное состояние — `PROTECTED`.
2. Физически оборвать VPN, не отключая Ethernet/Wi-Fi.
3. Guardian подтверждает `VPN_ROUTE_LOST` несколькими измерениями, а не одним ping.
4. В Shadow-журнале появляется `FAIL-CLOSED WOULD ACTIVATE`. В Automatic физический
   default route удаляется, но host-route до VPN-сервера сохраняется.
5. Выполняется только одна попытка reconnect, затем полная проверка.
6. До успешных IP/DNS/route/probe проверок состояние не становится `PROTECTED` и
   route не восстанавливается.
7. При превышении лимита — `LOCKDOWN`; Emergency Recovery возвращает сохранённый route.
8. В `data/incidents.jsonl` остаётся одна полная запись инцидента.

## Критерий

100 последовательных успешных циклов, ноль Direct-утечек, ноль невосстановимых
зависаний сети. Программная симуляция не заменяет этот физический тест.

