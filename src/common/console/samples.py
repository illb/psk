"""Sample messages taken from real CLI output, used by the showcase and tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sample:
    name: str
    markup: str
    """Message as callers write it today (line color only)."""
    marked: str
    """Same message with values marked by theme names ([value], [path], ...)."""
    plain: str
    """Visible text; every mode must render exactly these characters."""


SAMPLES: tuple[Sample, ...] = (
    Sample(
        "deploy-done",
        "[green]✅ 폴더 'app-vector-alerts'에서 2/2개 Alert Rules 배포 완료[/green]",
        "[ok]✅ 폴더 [path]'app-vector-alerts'[/path]에서 [value]2/2[/value]개 Alert Rules 배포 완료[/ok]",
        "✅ 폴더 'app-vector-alerts'에서 2/2개 Alert Rules 배포 완료",
    ),
    Sample(
        "quota",
        "[yellow]⚠️  CPU quota 80% 초과 - 대기 1,234ms[/yellow]",
        "[warn]⚠️  CPU quota [value]80%[/value] 초과 - 대기 [value]1,234ms[/value][/warn]",
        "⚠️  CPU quota 80% 초과 - 대기 1,234ms",
    ),
    Sample(
        "paren-call",
        "[cyan]3회 느림(대기 열 12건) (평균 4.5s)[/cyan]",
        "[cyan][value]3[/value]회 느림(대기 열 [value]12[/value]건) (평균 [value]4.5s[/value])[/cyan]",
        "3회 느림(대기 열 12건) (평균 4.5s)",
    ),
    Sample(
        "no-line-color",
        "TT 레코드 값 개수 20,000 초과, 값 1,000 넘은 유저 7일 평균",
        "TT 레코드 값 개수 [value]20,000[/value] 초과, 값 [value]1,000[/value] 넘은 유저 7일 평균",
        "TT 레코드 값 개수 20,000 초과, 값 1,000 넘은 유저 7일 평균",
    ),
    Sample(
        "path-url-const",
        "config=/etc/app/app.yaml url=https://grafana.example/d/abc?var-x=1 dryRun=True owner=None",
        "[key]config[/key]=[path]/etc/app/app.yaml[/path] [key]url[/key]=https://grafana.example/d/abc?var-x=1 "
        "[key]dryRun[/key]=True [key]owner[/key]=None",
        "config=/etc/app/app.yaml url=https://grafana.example/d/abc?var-x=1 dryRun=True owner=None",
    ),
    Sample(
        "key-colon",
        "Grafana URL: https://asdp-grafana.example/d/x?var-a=1 환경: production 비교 8개: 일치 8, 어긋남 0 시각 12:30",
        "Grafana URL: [path]https://asdp-grafana.example/d/x?var-a=1[/path] 환경: [value]production[/value] "
        "비교 8개: 일치 [value]8[/value], 어긋남 [value]0[/value] 시각 12:30",
        "Grafana URL: https://asdp-grafana.example/d/x?var-a=1 환경: production 비교 8개: 일치 8, 어긋남 0 시각 12:30",
    ),
    Sample(
        "error",
        "[red]✗ 조회 실패: HTTP 503 (재시도 3/3, 마지막 오류 'timeout after 30s')[/red]",
        "[err]✗ 조회 실패: HTTP [value]503[/value] (재시도 [value]3/3[/value], 마지막 오류 'timeout after 30s')[/err]",
        "✗ 조회 실패: HTTP 503 (재시도 3/3, 마지막 오류 'timeout after 30s')",
    ),
)

# A string that already carries ANSI codes, e.g. a pre-rendered table cell.
ANSI_SAMPLE = "\x1b[38;5;208mwarn 12\x1b[0m done 3/4"
ANSI_SAMPLE_PLAIN = "warn 12 done 3/4"
