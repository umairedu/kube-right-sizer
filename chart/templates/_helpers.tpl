{{- define "right-sizer.name" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "right-sizer.labels" -}}
app.kubernetes.io/name: kube-right-sizer
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{- define "right-sizer.slackSecret" -}}
{{- .Values.slack.existingSecret | default (printf "%s-slack" (include "right-sizer.name" .)) }}
{{- end }}
