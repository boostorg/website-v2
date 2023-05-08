{{/* vim: set filetype=sls sw=2 ts=2: */}}


{{- define "InitMethod" -}}
  {{- $major := .Capabilities.KubeVersion.Major -}}
  {{- $minor_ := ( splitList "+" .Capabilities.KubeVersion.Minor ) -}}
  {{- $minor := index $minor_ 0 -}}
  {{- if and (lt (int $major) 2) (lt (int $minor) 8) }}
    {{- printf "annotation" -}}
  {{- else -}}
    {{- printf "spec" -}}
  {{- end -}} {{/* if */}}
{{- end -}} {{/* define */}}

