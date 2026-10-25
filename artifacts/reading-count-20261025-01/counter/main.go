package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"image"
	_ "image/gif"
	_ "image/jpeg"
	_ "image/png"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"

	"globe-reading-fit-counter/tokenizer"
)

const repo = "/Users/sflynn/Downloads/congressional globe project"
const ollamaBlobs = "/Users/sflynn/.ollama/models/blobs"

var imageTag = regexp.MustCompile(`\[img-(\d+)\]`)

type Manifest struct { Requests []Request `json:"requests"` }
type Message struct { Role string `json:"role"`; Content string `json:"content"` }
type ImageRecord struct { ID string `json:"id"`; Path string `json:"path"`; SHA string `json:"sha256"` }
type Request struct {
	Model string `json:"model"`
	Digest string `json:"model_digest"`
	Unit string `json:"unit_id"`
	Hash string `json:"request_sha256"`
	Messages []Message `json:"messages_without_image_payloads"`
	Images []ImageRecord `json:"images"`
	Options struct { NumCtx int `json:"num_ctx"`; NumPredict int `json:"num_predict"` } `json:"options"`
}
type Asset struct { Tokenizer string; TokenizerConfig string; Config string; Renderer string }
type ImageCount struct { ID string `json:"id"`; Path string `json:"path"`; SHA string `json:"sha256"`; Width int `json:"width"`; Height int `json:"height"`; ExpandedTokens int `json:"expanded_tokens"` }
type Result struct {
	Model string `json:"model"`; Digest string `json:"model_digest"`; Unit string `json:"unit_id"`; RequestSHA string `json:"request_sha256"`
	RenderedPromptSHA string `json:"rendered_prompt_sha256"`; TextTokenCount int `json:"text_tokens"`; ImageTokenCount int `json:"image_tokens"`; TotalInputTokens int `json:"total_input_tokens"`
	NumCtx int `json:"requested_num_ctx"`; NumPredict int `json:"requested_num_predict"`; RequestedEnvelopeFits bool `json:"fits_requested_context_with_output_reserve"`
	Images []ImageCount `json:"images"`
}

func mustRead(path string) []byte { b,e:=os.ReadFile(path); if e!=nil { panic(e) }; return b }
func hash(b []byte) string { h:=sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func mustHashFile(path, expected string) []byte { b:=mustRead(path); if hash(b)!=expected { panic("hash mismatch: "+path) }; return b }
func modelAsset(model string) Asset {
	switch model {
	case "qwen3.8:27b-mlx": return Asset{ollamaBlobs+"/sha256-0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3",ollamaBlobs+"/sha256-5a205aa76328f59df93a9091d0496aeda4615c6b0c495cbd37e14c79c0cd0f94",ollamaBlobs+"/sha256-af908e4b42c018ef923ebc38c16083aa75051dc3778b92b1443adabd2cab2267","qwen3.8"}
	case "gemma4:31b-mlx": return Asset{ollamaBlobs+"/sha256-cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f",ollamaBlobs+"/sha256-a284d1243b62be31faa9c13e1c28cece940c4abaa7bd9ad87b94f61b40687200",ollamaBlobs+"/sha256-84b13502877928cc9db31c121034dc1ed6578921eaa4a5c2f504707d5d1db0b0","gemma4-large"}
	case "muse-glimmer:30b-mlx": return Asset{ollamaBlobs+"/sha256-8a25643f212b3e81a410b8afd0538b02ad30db4b22de863bde2e5006603afa2d",ollamaBlobs+"/sha256-2c49783174e680e3a7f41d40bc7a611affa67cb3e05d41acffb97d44f023283a",ollamaBlobs+"/sha256-c769cd377cae4cf5417e4abb24fce051acc53dde3660c96fa878f6ec98eb28ff","glimmer"}
	default: panic("unsupported model: "+model)
	}
}
func loadTokenizer(a Asset) *tokenizer.Tokenizer {
	cfg:=&tokenizer.TokenizerConfig{TokenizerConfigJSON:mustRead(a.TokenizerConfig),ConfigJSON:mustRead(a.Config)}
	t,err:=tokenizer.LoadFromBytesWithConfig(mustRead(a.Tokenizer),cfg);if err!=nil{panic(err)};return t
}
func imageTagContent(content string,count,offset int) (string,int) {
	if count==0{return content,offset}; if strings.Contains(content,"[img-"){return content,offset+count}
	var prefix strings.Builder
	for i:=0;i<count;i++ { tag:=fmt.Sprintf("[img-%d]",offset+i);if strings.Contains(content,"[img]"){content=strings.Replace(content,"[img]",tag,1)}else{prefix.WriteString(tag)} }
	if prefix.Len()>0&&content!="" { first,_:=utf8.DecodeRuneInString(content);if !unicode.IsSpace(first){prefix.WriteByte(' ')} }
	return prefix.String()+content,offset+count
}
func render(r Request) string {
	if len(r.Messages)!=2||r.Messages[0].Role!="system"||r.Messages[1].Role!="user" { panic("unexpected frozen message shape") }
	system:=strings.TrimSpace(r.Messages[0].Content); user:=r.Messages[1].Content
	content,_:=imageTagContent(user,len(r.Images),0)
	switch modelAsset(r.Model).Renderer {
	case "qwen3.8":
		return "<|im_start|>system\n"+system+"<|im_end|>\n<|im_start|>user\n"+strings.TrimSpace(content)+"<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
	case "gemma4-large":
		return "<bos><|turn>system\n"+system+"<turn|>\n<|turn>user\n"+strings.TrimSpace(content)+"<turn|>\n<|turn>model\n<|channel>thought\n<channel|>"
	case "glimmer":
		s:=strings.NewReplacer("Reasoning effort","Reasoning strength","Reasoning Effort","Reasoning Strength","reasoning effort","reasoning strength","REASONING EFFORT","REASONING STRENGTH").Replace(system)
		if !strings.Contains(strings.ToLower(s),"reasoning strength") { s+="\n\nReasoning strength: none." }
		return "<|begin_of_text|><|start|>system<|message|>"+s+"\n\n# Valid recipients: \"self\", \"user\".<|eot|><|start|>user<|message|>"+content+"<|eot|><|start|>assistant"
	default: panic("renderer")
	}
}
func qwenExpansion(w,h,patch,merge int) int {
	factor:=patch*merge; longer,shorter:=float64(max(w,h)),float64(min(w,h));if longer/shorter>200 { panic("image aspect ratio exceeds source constraint") }
	hbar:=math.RoundToEven(float64(h)/float64(factor))*float64(factor);wbar:=math.RoundToEven(float64(w)/float64(factor))*float64(factor)
	const minPixels=65536.0;const maxPixels=16777216.0
	if hbar*wbar>maxPixels { beta:=math.Sqrt(float64(h)*float64(w)/maxPixels);hbar=math.Max(float64(factor),math.Floor(float64(h)/beta/float64(factor))*float64(factor));wbar=math.Max(float64(factor),math.Floor(float64(w)/beta/float64(factor))*float64(factor)) } else if hbar*wbar<minPixels { beta:=math.Sqrt(minPixels/(float64(h)*float64(w)));hbar=math.Ceil(float64(h)*beta/float64(factor))*float64(factor);wbar=math.Ceil(float64(w)*beta/float64(factor))*float64(factor) }
	return int(hbar/float64(patch)/float64(merge))*int(wbar/float64(patch)/float64(merge))+2
}
func gemmaSize(h,w,patch,pool,budget int)(int,int){side:=float64(patch*pool);targetPx:=float64(budget)*side*side;factor:=math.Sqrt(targetPx/(float64(h)*float64(w)));th:=math.Floor(factor*float64(h)/side)*side;tw:=math.Floor(factor*float64(w)/side)*side
	if th==0&&tw==0 {panic("image too small for Gemma")};maxSide:=float64(budget)*side
	if th==0 {th=side;tw=math.Min(math.Floor(float64(w)/float64(h))*side,maxSide)} else if tw==0 {tw=side;th=math.Min(math.Floor(float64(h)/float64(w))*side,maxSide)}
	if th*tw>targetPx||th>maxSide||tw>maxSide {panic("Gemma resize over budget")};return int(th),int(tw)
}
func gemmaExpansion(w,h,patch,pool int) int { var th,tw int;for _,b:=range []int{70,140,280,560,1120}{th,tw=gemmaSize(h,w,patch,pool,b);if th>=h&&tw>=w{break}};return (th/patch)*(tw/patch)/(pool*pool)+2 }
func glimmerExpansion(w,h,stride,maxTokens int) int {
	rows:=float64(h)/float64(stride);cols:=float64(w)/float64(stride);ratio:=cols/rows
	if rows*cols>float64(maxTokens){rows=math.Sqrt(float64(maxTokens)/ratio);cols=rows*ratio}
	rs:=[]int{int(math.Floor(rows)),int(math.Ceil(rows))};cs:=[]int{int(math.Floor(cols)),int(math.Ceil(cols))};bestR,bestC:=0,0;bestDelta:=math.Inf(1);seen:=map[[2]int]bool{}
	for _,rr:=range rs {for _,cc:=range cs {k:=[2]int{rr,cc};if seen[k]||rr<1||cc<1||rr*cc>maxTokens{continue};seen[k]=true;delta:=math.Abs(float64(rr)/float64(cc)-float64(h)/float64(w));if delta<bestDelta||(delta==bestDelta&&rr*cc>bestR*bestC){bestR,bestC,bestDelta=rr,cc,delta}}}
	if bestR==0 {bestR=max(1,int(math.Round(rows)));bestC=max(1,int(math.Round(cols)))};return bestR*bestC+2
}
func imageTokens(model string, images []ImageRecord) []ImageCount {
	var out []ImageCount; a:=modelAsset(model);var cfg map[string]any;if err:=json.Unmarshal(mustRead(a.Config),&cfg);err!=nil{panic(err)}
	vision:=map[string]any{};switch model {case "qwen3.8:27b-mlx":vision=cfg["vision_config"].(map[string]any);case "gemma4:31b-mlx":vision=cfg["vision_config"].(map[string]any)}
	for _,im:=range images {
		p:=filepath.Join(repo,im.Path);data:=mustHashFile(p,im.SHA);c,_,err:=image.DecodeConfig(bytes.NewReader(data));if err!=nil{panic(err)}
		var n int
		switch model {
		case "qwen3.8:27b-mlx": n=qwenExpansion(c.Width,c.Height,int(vision["patch_size"].(float64)),int(vision["spatial_merge_size"].(float64)))
		case "gemma4:31b-mlx": n=gemmaExpansion(c.Width,c.Height,int(vision["patch_size"].(float64)),int(vision["pooling_kernel_size"].(float64)))
		case "muse-glimmer:30b-mlx": n=glimmerExpansion(c.Width,c.Height,int(cfg["vision_patch_size"].(float64)*cfg["vision_downsample_factor"].(float64)),4096)
		}
		out=append(out,ImageCount{ID:im.ID,Path:im.Path,SHA:im.SHA,Width:c.Width,Height:c.Height,ExpandedTokens:n})
	}
	return out
}
func textTokens(t *tokenizer.Tokenizer,prompt string) int {
	indices:=imageTag.FindAllStringSubmatchIndex(prompt,-1);prev:=0;total:=0
	for i,m:=range indices {seg:=prompt[prev:m[0]];total+=len(t.Encode(seg,i==0&&t.AddBOS()));id,err:=strconv.Atoi(prompt[m[2]:m[3]]);if err!=nil{panic(err)};if id<0{panic("negative image id")};prev=m[1]}
	seg:=prompt[prev:];total+=len(t.Encode(seg,len(indices)==0&&t.AddBOS()))
	if len(indices)==0&&t.AddBOS(){ /* BOS is already counted above. */ }
	return total
}
func main() {
	manifestPath:=filepath.Join(repo,"artifacts/reading-launch-20261025-01/requests.json"); if len(os.Args)>1 { manifestPath=os.Args[1] }; manifestBytes:=mustRead(manifestPath);var m Manifest;if err:=json.Unmarshal(manifestBytes,&m);err!=nil{panic(err)}
	fmt.Fprintf(os.Stderr,"manifest_sha256=%s requests=%d\n",hash(manifestBytes),len(m.Requests))
	cache:=map[string]*tokenizer.Tokenizer{}
	results:=make([]Result,0,len(m.Requests))
	for _,r:=range m.Requests {
		t:=cache[r.Model];if t==nil{t=loadTokenizer(modelAsset(r.Model));cache[r.Model]=t}
		prompt:=render(r);images:=imageTokens(r.Model,r.Images);imgN:=0;for _,im:=range images{imgN+=im.ExpandedTokens}
		textN:=textTokens(t,prompt);total:=textN+imgN
		results=append(results,Result{Model:r.Model,Digest:r.Digest,Unit:r.Unit,RequestSHA:r.Hash,RenderedPromptSHA:hash([]byte(prompt)),TextTokenCount:textN,ImageTokenCount:imgN,TotalInputTokens:total,NumCtx:r.Options.NumCtx,NumPredict:r.Options.NumPredict,RequestedEnvelopeFits:total+r.Options.NumPredict<=r.Options.NumCtx,Images:images})
	}
	enc:=json.NewEncoder(os.Stdout);enc.SetIndent("","  ");if err:=enc.Encode(results);err!=nil{panic(err)}
}
