{{/*
Chart name
*/}}
{{- define "runboat.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fullname
*/}}
{{- define "runboat.fullname" -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "runboat.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "runboat.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "runboat.selectorLabels" -}}
app.kubernetes.io/name: {{ include "runboat.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
PostgreSQL host — auto-derive from CNPG or use explicit override
*/}}
{{- define "runboat.dbHost" -}}
{{- if .Values.postgresql.host }}
{{- .Values.postgresql.host }}
{{- else }}
{{- printf "runboat-db-rw.%s.svc.cluster.local" .Values.namespace }}
{{- end }}
{{- end }}

{{/*
Build PGHOST env for builds
*/}}
{{- define "runboat.buildEnv" -}}
{{- $env := dict "PGHOST" (include "runboat.dbHost" .) "PGPORT" .Values.postgresql.port "PGUSER" .Values.postgresql.user }}
{{- range $k, $v := .Values.config.buildEnv }}
{{- $_ := set $env $k $v }}
{{- end }}
{{- $env | toJson }}
{{- end }}

{{/*
Build secret env for builds
*/}}
{{- define "runboat.buildSecretEnv" -}}
{{- $env := dict "PGPASSWORD" .Values.postgresql.password }}
{{- range $k, $v := .Values.config.buildSecretEnv }}
{{- $_ := set $env $k $v }}
{{- end }}
{{- $env | toJson }}
{{- end }}

{{/*
Build template vars
*/}}
{{- define "runboat.buildTemplateVars" -}}
{{- $vars := dict "storageClassName" .Values.buildStorage.storageClassName }}
{{- range $k, $v := .Values.config.buildTemplateVars }}
{{- $_ := set $vars $k $v }}
{{- end }}
{{- $vars | toJson }}
{{- end }}

{{/*
Repos JSON
*/}}
{{- define "runboat.repos" -}}
{{- .Values.repos | toJson }}
{{- end }}
