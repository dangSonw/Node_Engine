[[vk::combinedImageSampler]] Texture2D<float4> Layer : register(t0, space2);
[[vk::combinedImageSampler]] SamplerState LayerSampler : register(s0, space2);
cbuffer Settings : register(b0, space3) { float4 parameters; };
float4 main(float2 uv : TEXCOORD0) : SV_Target0 {
    float4 color = Layer.Sample(LayerSampler, uv);
    if (parameters.x != 0 && color.a > 0) {
        float3 rgb = saturate(color.rgb / color.a);
        rgb = select(rgb <= .04045, rgb / 12.92, pow((rgb + .055) / 1.055, 2.4));
        color.rgb = rgb * color.a;
    }
    return color;
}
