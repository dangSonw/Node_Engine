// SDL's SPIR-V backend requires a combined sampler in set 2, binding 0.
[[vk::combinedImageSampler]] Texture2D<float4> BaseColor : register(t0, space2);
[[vk::combinedImageSampler]] SamplerState TextureSampler : register(s0, space2);
[[vk::combinedImageSampler]] Texture2D<float4> NormalMap : register(t1, space2);
[[vk::combinedImageSampler]] SamplerState NormalSampler : register(s1, space2);
cbuffer Material : register(b0, space3) {
    float4 parameters;
    float4 baseColor;
    float4 uvBounds;
    float4 pbr;
    float4 emission;
    float4 lightDirectionIntensity[4];
    float4 lightColorKind[4];
    float4 cameraPosition;
};
struct Input {
    float4 Color : TEXCOORD0;
    float2 UV : TEXCOORD1;
    float Shade : TEXCOORD2;
    float3 WorldPosition : TEXCOORD3;
    float3 WorldNormal : TEXCOORD4;
};
float4 main(Input input) : SV_Target0 {
    float2 uv = parameters.w != 0 ? clamp(input.UV, uvBounds.xy, uvBounds.zw) : input.UV;
    float4 color = input.Color * baseColor * BaseColor.Sample(TextureSampler, uv);
    if (pbr.z != 0 && parameters.z == 0) {
        float3 N = normalize(input.WorldNormal);
        if (pbr.w != 0) {
            float3 encoded = NormalMap.Sample(NormalSampler, uv).xyz * 2.0 - 1.0;
            encoded.xy *= pbr.w;
            float3 up = abs(N.y) < .99 ? float3(0,1,0) : float3(1,0,0);
            float3 T = normalize(cross(up, N));
            float3 B = normalize(cross(N, T));
            N = normalize(T * encoded.x + B * encoded.y + N * max(encoded.z, .05));
        }
        float3 V = normalize(cameraPosition.xyz - input.WorldPosition);
        float NdotV = max(saturate(dot(N, V)), .001);
        float roughness = clamp(pbr.y, .045, 1.0);
        float alpha = roughness * roughness;
        float alpha2 = alpha * alpha;
        float k = (roughness + 1.0) * (roughness + 1.0) / 8.0;
        float Gv = NdotV / (NdotV * (1.0 - k) + k);
        float3 F0 = lerp(float3(.04,.04,.04), color.rgb, pbr.x);
        float3 lighting = 0;
        for (int light = 0; light < 4; ++light) {
            if (lightDirectionIntensity[light].w <= 0) continue;
            float3 toLight = lightDirectionIntensity[light].xyz - input.WorldPosition * lightColorKind[light].w;
            float distanceToLight = length(toLight);
            float3 L = normalize(toLight);
            float3 H = normalize(L + V);
            float NdotL = saturate(dot(N, L));
            float NdotH = max(saturate(dot(N, H)), .001);
            float VdotH = max(saturate(dot(V, H)), .001);
            float denom = NdotH * NdotH * (alpha2 - 1.0) + 1.0;
            float D = alpha2 / max(3.14159265 * denom * denom, .0001);
            float Gl = NdotL / (NdotL * (1.0 - k) + k);
            float3 F = F0 + (1.0 - F0) * pow(1.0 - VdotH, 5.0);
            float3 specular = (D * Gv * Gl * F) / max(4.0 * NdotV * NdotL, .001);
            float3 diffuse = (1.0 - F) * (1.0 - pbr.x) * color.rgb / 3.14159265;
            float attenuation = lightColorKind[light].w == 0 ? 1.0 : 1.0 / max(1.0 + distanceToLight * distanceToLight, 1.0);
            lighting += (diffuse + specular) * lightColorKind[light].rgb * lightDirectionIntensity[light].w * attenuation * NdotL;
        }
        color.rgb = lighting + emission.rgb;
    } else {
        color.rgb *= parameters.z != 0 ? 1 : input.Shade;
    }
    if (parameters.x == 1 && color.a < parameters.y) discard;
    if (parameters.x != 2) color.a = 1;
    return color;
}
