cbuffer Transform : register(b0, space1) {
    float4x4 mvp;
    float4 uvTransform;
    float4x4 model;
};
struct Input {
    float3 Position : TEXCOORD0;
    float4 Color : TEXCOORD1;
    float2 UV : TEXCOORD2;
    float Shade : TEXCOORD3;
    float3 Normal : TEXCOORD4;
};
struct Output {
    float4 Color : TEXCOORD0;
    float2 UV : TEXCOORD1;
    float Shade : TEXCOORD2;
    float3 WorldPosition : TEXCOORD3;
    float3 WorldNormal : TEXCOORD4;
    float4 Position : SV_Position;
};
Output main(Input input) {
    Output output;
    output.Position = mul(mvp, float4(input.Position, 1));
    output.Color = input.Color;
    output.UV = input.UV * uvTransform.xy + uvTransform.zw;
    output.Shade = input.Shade;
    output.WorldPosition = mul(model, float4(input.Position, 1)).xyz;
    output.WorldNormal = normalize(mul(model, float4(input.Normal, 0)).xyz);
    return output;
}
