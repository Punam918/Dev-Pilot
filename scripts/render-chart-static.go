// Offline validation aid, not a replacement for Helm. Executes the actual chart
// files through Go text/template with ONLY the functions this chart uses.
// No Kubernetes capabilities, Helm schema loading, Sprig compliance or API validation.
// Usage: python scripts/chart-input.py | go run scripts/render-chart-static.go helm/devpilot
package main
import (
 "bytes"
 "crypto/sha256"
 "encoding/json"
 "fmt"
 "io"
 "os"
 "os/exec"
 "path/filepath"
 "strconv"
 "strings"
 "text/template"
)
func main(){
 if len(os.Args)!=2 { panic("Pass helm/devpilot") }
 input,err:=io.ReadAll(os.Stdin);if err!=nil {panic(err)}
 var data map[string]interface{};if err=json.Unmarshal(input,&data);err!=nil{panic(err)}
 var tpl *template.Template
 funcs:=template.FuncMap{
  "quote":func(v interface{})string{return strconv.Quote(fmt.Sprint(v))},
  "trunc":func(n int,s string)string{if len(s)>n{return s[:n]};return s},
  "trimSuffix":func(suffix,s string)string{return strings.TrimSuffix(s,suffix)},
  "nindent":func(n int,s string)string{pad:=strings.Repeat(" ",n);return "\n"+pad+strings.ReplaceAll(strings.TrimRight(s,"\n"),"\n","\n"+pad)},
  "toJson":func(v interface{})(string,error){b,e:=json.Marshal(v);return string(b),e},
  "toYaml":func(v interface{})(string,error){b,e:=json.Marshal(v);if e!=nil{return "",e};c:=exec.Command("python3","-c","import json,sys,yaml;print(yaml.safe_dump(json.load(sys.stdin),sort_keys=False),end='')");c.Stdin=bytes.NewReader(b);out,e:=c.Output();return string(out),e},
  "sha256sum":func(s string)string{return fmt.Sprintf("%x",sha256.Sum256([]byte(s)))},
  "default":func(d,v interface{})interface{}{if v==nil||v==""||v==false{return d};return v},
  "int":func(v interface{})int{n,_:=strconv.Atoi(fmt.Sprint(v));return n},
  "add":func(a,b int)int{return a+b},
  "fail":func(s string)(string,error){return "",fmt.Errorf("chart guard: %s",s)},
  "include":func(name string,v interface{})(string,error){var b bytes.Buffer;e:=tpl.ExecuteTemplate(&b,name,v);return b.String(),e},
 }
 tpl=template.New("chart").Funcs(funcs).Option("missingkey=error")
 paths,err:=filepath.Glob(filepath.Join(os.Args[1],"templates","*"));if err!=nil{panic(err)}
 for _,p:=range paths{if filepath.Base(p)=="NOTES.txt"{continue};b,e:=os.ReadFile(p);if e!=nil{panic(e)};name:="devpilot/templates/"+filepath.Base(p);if _,e=tpl.New(name).Parse(string(b));e!=nil{panic(e)}}
 for _,p:=range paths{if filepath.Ext(p)!=".yaml"{continue};var b bytes.Buffer;if e:=tpl.ExecuteTemplate(&b,"devpilot/templates/"+filepath.Base(p),data);e!=nil{panic(e)};if strings.TrimSpace(b.String())!=""{fmt.Printf("---\n# Source: %s (static Go rendering, NOT helm)\n%s\n",p,b.String())}}
}
