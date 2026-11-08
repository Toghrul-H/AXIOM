import { DemonstratorApplicationDetail } from "@/components/demonstrator-application-detail";
export default async function Page({params}:{params:Promise<{vacancyId:string;applicationId:string}>}){const {vacancyId,applicationId}=await params;return <DemonstratorApplicationDetail vacancyId={Number(vacancyId)} applicationId={Number(applicationId)}/>}
